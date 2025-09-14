import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")
try:
    client = Groq(api_key=api_key)
except Exception as e:
    raise RuntimeError(f"Failed to initialize Groq client: {e}")

def generate_questions(role, domain, mode, num_questions=5, question_set="Standard"):
    prompt = (
        f"Generate exactly {num_questions} {'technical' if mode == 'Technical Interview' else 'behavioral'} "
        f"interview questions for a {role} role in {domain if domain else 'general software engineering'} "
        f"using {question_set} style. Format as a numbered list (e.g., '1. Question text'). "
        f"Ensure each question is non-empty and starts with a number."
    )
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview question generator. Return questions in a numbered list format (e.g., '1. Question text')."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=1
            )
            content = completion.choices[0].message.content.strip()
            print(f"Raw API response: {content}")  # Debug log
            questions = [q.strip() for q in content.split("\n") if q.strip() and q[0].isdigit()]
            if len(questions) >= num_questions:
                print(f"Generated {len(questions)} questions: {questions}")
                return questions[:num_questions]
            else:
                print(f"Warning: Only {len(questions)} questions generated, retrying...")
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    print(f"Fallback triggered: Returning {num_questions} dummy questions")
    return [f"Dummy question {i + 1}: Describe a {mode.lower()} challenge for {role} role" for i in range(num_questions)]

def evaluate_answer(question, answer, mode):
    prompt = (
        f"Evaluate this {'technical' if mode == 'Technical Interview' else 'behavioral'} interview answer for question: '{question}'\n"
        f"Answer: '{answer}'\n"
        f"Assess clarity, correctness, completeness, and technical accuracy. Provide detailed feedback, a score out of 10, and suggestions in plain text."
    )
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview evaluator. Provide feedback in plain text, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=1
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    return "Error: Failed to evaluate answer after retries"

def generate_summary(role, mode, questions, responses, feedbacks, question_set="Standard"):
    if not responses or all(r == "Skipped" for r in responses):
        prompt = (
            f"The user skipped all questions in an interview for a {role} role in {mode} mode with {question_set} question set. "
            f"Provide general advice. Format with sections: General Advice, Areas of Strength, Areas to Improve, Suggested Resources. "
            f"Use plain text and bullet points."
        )
    else:
        prompt = f"Summarize the interview for a {role} in {mode} mode with {question_set} question set.\n"
        for i, (q, resp, fb) in enumerate(zip(questions, responses, feedbacks)):
            prompt += f"Question {i+1}: {q}\nResponse: {resp}\nFeedback: {fb}\n\n"
        prompt += (
            "Generate a professional summary in plain text with sections: Questions and Responses, Areas of Strength, "
            "Areas to Improve, Suggested Resources, Overall Score. Use bullet points and regular hyphens."
        )
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview summarizer. Format output as plain text with bullet points under headers, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=1
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    return "Error: Failed to generate summary after retries"