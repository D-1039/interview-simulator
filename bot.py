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
    prompt = f"Generate exactly {num_questions} {'technical' if mode == 'Technical Interview' else 'behavioral'} interview questions for a {role} role in {domain if domain else 'general software engineering'} using {question_set} style."
    for attempt in range(3):  # Retry up to 3 times
        try:
            completion = client.chat.completions.create(
                model="mixtral-8x7b-32768",  # Valid Groq model
                messages=[{"role": "system", "content": "You are an interview question generator."}, {"role": "user", "content": prompt}],
                max_tokens=1000  # Changed from max_completion_tokens
            )
            return completion.choices[0].message.content.split("\n")
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise e
    raise Exception("Failed to generate questions after retries")

def evaluate_answer(question, answer, mode):
    prompt = f"Evaluate the following answer for a {mode} question: '{question}'. Answer: '{answer}'. Provide feedback on clarity, correctness, completeness, and technical accuracy (if applicable)."
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "system", "content": "You are an answer evaluator."}, {"role": "user", "content": prompt}],
                max_tokens=500
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    raise Exception("Failed to evaluate answer after retries")

def generate_summary(role, mode, questions, responses, feedbacks, question_set):
    prompt = f"Generate a summary for a {mode} interview for a {role} role. Questions: {questions}. Responses: {responses}. Feedbacks: {feedbacks}."
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "system", "content": "You are a summary generator."}, {"role": "user", "content": prompt}],
                max_tokens=1000
            )
            return completion.choices[0].message.content
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    raise Exception("Failed to generate summary after retries")