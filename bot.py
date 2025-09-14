import os
import time
import re
import sqlite3
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import streamlit as st

# Load environment variables
load_dotenv()

# Get Hugging Face token: Use st.secrets in cloud, fallback to env
if "HF_TOKEN" in st.secrets:
    token = st.secrets["HF_TOKEN"]
else:
    token = os.getenv("HF_TOKEN")

# Validate token early
if not token:
    st.error("HF_TOKEN is missing. Please set it in Streamlit secrets (cloud) or .env file (local). Get a free token from https://huggingface.co/settings/tokens")
    client = None
else:
    try:
        # Test client initialization with token
        client = InferenceClient(token=token)
        # Optional: Test a simple call to verify (comment out if rate limits are an issue)
        # _ = client.text_generation("Test", model="gpt2", max_new_tokens=1)
        st.success("Hugging Face client initialized successfully.")  # Remove in production
    except Exception as e:
        st.error(f"Invalid HF_TOKEN: {str(e)}. Regenerate a new token at https://huggingface.co/settings/tokens and ensure you've accepted the model terms at https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3")
        client = None

def init_db():
    conn = sqlite3.connect("interview.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS history (
        user_id TEXT, 
        timestamp TEXT, 
        role TEXT, 
        mode TEXT, 
        question_set TEXT, 
        question TEXT, 
        answer TEXT, 
        feedback TEXT, 
        score INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS leaderboard (
        user_id TEXT PRIMARY KEY, 
        total_score INTEGER, 
        attempts INTEGER
    )""")
    conn.commit()
    conn.close()

def generate_questions(role, domain, mode, num_questions=5, question_set="Standard", difficulty="Medium"):
    if not role.strip() or len(role) > 100:
        raise ValueError("Role must be 1-100 characters")
    if domain and len(domain) > 100:
        raise ValueError("Domain must be 1-100 characters")
    
    if client is None:
        st.warning("Using dummy questions due to missing/invalid HF_TOKEN.")
        return [f"Dummy question {i + 1}: Describe a {mode.lower()} challenge for {role} role" for i in range(num_questions)]
    
    prompt = (
        f"Generate exactly {num_questions} {'technical' if mode == 'Technical Interview' else 'behavioral'} "
        f"interview questions for a {role} role in {domain if domain else 'general software engineering'} "
        f"using {question_set} style at {difficulty} difficulty. "
        f"Format as a numbered list (e.g., '1. Question text'). "
        f"Ensure each question is non-empty and starts with a number."
    )
    for attempt in range(3):
        try:
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are an interview question generator. Return questions in a numbered list format (e.g., '1. Question text')."},
                    {"role": "user", "content": prompt}
                ],
                model="mistralai/Mistral-7B-Instruct-v0.3",
                max_tokens=512,
                temperature=1
            )
            content = response.choices[0].message.content.strip()
            questions = [q.strip() for q in content.split("\n") if q.strip() and q[0].isdigit()]
            if len(questions) >= num_questions:
                return questions[:num_questions]
            time.sleep(2 ** attempt)
        except Exception as e:
            if "rate limit" in str(e).lower() or "unauthorized" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Failed to generate questions: {e}")
    st.warning("Using dummy questions after API retries failed.")
    return [f"Dummy question {i + 1}: Describe a {mode.lower()} challenge for {role} role" for i in range(num_questions)]

def evaluate_answer(question, answer, mode):
    if not answer.strip():
        raise ValueError("Answer cannot be empty")
    
    if client is None:
        return "Evaluation unavailable due to missing HF_TOKEN. Please provide a valid token.", 0
    
    prompt = (
        f"Evaluate this {'technical' if mode == 'Technical Interview' else 'behavioral'} interview answer for question: '{question}'\n"
        f"Answer: '{answer}'\n"
        f"Assess clarity, correctness, completeness, and technical accuracy. Provide detailed feedback, a score out of 10, and suggestions in plain text."
    )
    for attempt in range(3):
        try:
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are an interview evaluator. Provide feedback in plain text, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                model="mistralai/Mistral-7B-Instruct-v0.3",
                max_tokens=512,
                temperature=1
            )
            feedback = response.choices[0].message.content.strip()
            score_match = re.search(r"Score:\s*(\d+)/10", feedback)
            score = int(score_match.group(1)) if score_match else 0
            return feedback, score
        except Exception as e:
            if "rate limit" in str(e).lower() or "unauthorized" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Failed to evaluate answer: {e}")
    return "Error: Failed to evaluate answer after retries", 0

def generate_summary(role, mode, questions, responses, feedbacks, question_set="Standard", difficulty="Medium"):
    if client is None:
        return "Summary unavailable due to missing HF_TOKEN. Please provide a valid token. General advice: Practice more on key areas."
    
    if not responses or all(r == "Skipped" for r in responses):
        prompt = (
            f"The user skipped all questions in an interview for a {role} role in {mode} mode with {question_set} question set at {difficulty} difficulty. "
            f"Provide general advice. Format with sections: General Advice, Areas of Strength, Areas to Improve, Suggested Resources. "
            f"Use plain text and bullet points."
        )
    else:
        prompt = f"Summarize the interview for a {role} in {mode} mode with {question_set} question set at {difficulty} difficulty.\n"
        for i, (q, resp, fb) in enumerate(zip(questions, responses, feedbacks)):
            prompt += f"Question {i+1}: {q}\nResponse: {resp}\nFeedback: {fb}\n\n"
        prompt += (
            "Generate a professional summary in plain text with sections: Questions and Responses, Areas of Strength, "
            "Areas to Improve, Suggested Resources, Overall Score. Use bullet points and regular hyphens."
        )
    for attempt in range(3):
        try:
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are an interview summarizer. Format output as plain text with bullet points under headers, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                model="mistralai/Mistral-7B-Instruct-v0.3",
                max_tokens=512,
                temperature=1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower() or "unauthorized" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Failed to generate summary: {e}")
    return "Error: Failed to generate summary after retries"