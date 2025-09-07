from groq import Groq
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_questions(role, domain, mode, num_questions=5, question_set="Standard"):
    prompt = f"Generate exactly {num_questions} {'technical' if mode == 'Technical' else 'behavioral'} interview questions for a {role} role"
    if domain:
        prompt += f" in the {domain} domain"
    if mode == "Behavioral":
        prompt += ". Each question must be behavioral, focusing on past experiences, soft skills, leadership, collaboration, or decision-making, and structured in STAR (Situation, Task, Action, Result) format. Questions should ask for specific scenarios and avoid technical implementation details like algorithms or complexity."
        if question_set == "FAANG-style":
            prompt += " Tailor questions to reflect FAANG company expectations, emphasizing high-impact scenarios, scalable decision-making, or cross-functional collaboration in a technical context, while remaining strictly behavioral and avoiding technical details like coding or system design."
        elif question_set == "STAR-based":
            prompt += " Each question should be a single, cohesive prompt with context, asking the candidate to describe a scenario and respond using the STAR format (Situation, Task, Action, Result). Do not split STAR components into separate questions."
        else:
            prompt += " Use STAR format without splitting components."
    else:  # Technical mode
        if question_set == "FAANG-style":
            prompt += " tailored to FAANG company technical interviews, focusing on algorithmic complexity, system design, and technical problem-solving."
        else:
            prompt += " focusing on technical skills and problem-solving."
    prompt += f". List them as a numbered list with exactly {num_questions} questions, ensuring each is relevant to the role and domain."
    
    for attempt in range(3):  # Retry up to 3 times
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview question generator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                max_completion_tokens=512,
                top_p=1,
                stream=False
            )
            questions = completion.choices[0].message.content.strip().split("\n")
            questions = [q.strip() for q in questions if q.strip() and q[0].isdigit()]
            if len(questions) >= num_questions:
                return questions[:num_questions]
            else:
                time.sleep(2 ** attempt)  # Retry if not enough questions
                continue
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise e
    raise Exception("Failed to generate questions after retries")

def evaluate_answer(question, answer, mode):
    prompt = f"Evaluate this {'technical' if mode == 'Technical' else 'behavioral'} interview answer for question: '{question}'\nAnswer: '{answer}'\n"
    prompt += "Assess the following criteria:\n"
    prompt += "- Clarity: Is the answer clear, well-structured, and easy to understand?\n"
    prompt += "- Correctness: Is the answer factually accurate (for technical) or appropriate and relevant (for behavioral)?\n"
    prompt += "- Completeness: Does the answer fully address all parts of the question, including STAR components for behavioral questions?\n"
    if mode == "Behavioral":
        prompt += "- Real-world examples: Does the answer include specific, relevant real-world examples in STAR format?\n"
    else:
        prompt += "- Technical accuracy: Are the technical details precise and correct?\n"
    prompt += "Provide detailed feedback, a score out of 10, and specific suggestions for improvement in plain text."
    
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview evaluator. Provide feedback in plain text, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                max_completion_tokens=512,
                top_p=1,
                stream=False
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    raise Exception("Failed to evaluate answer after retries")

def generate_summary(role, mode, questions, responses, feedbacks, question_set="Standard"):
    if not responses:
        prompt = f"The user skipped all questions in an interview for a {role} role in {mode} mode with {question_set} question set. The questions were:\n"
        for i, q in enumerate(questions):
            prompt += f"Question {i+1}: {q}\n"
        prompt += "Since no responses were provided, a detailed summary cannot be generated. Instead, provide general advice for approaching these {'technical' if mode == 'Technical' else 'behavioral'} questions. Format the output with the following sections, each starting on a new line with a clear header and using bullet points:\n"
        prompt += "- General Advice: Provide tips for approaching the questions.\n"
        prompt += "- Areas of Strength: Highlight the user's engagement with the interview setup.\n"
        prompt += "- Areas to Improve: Emphasize the importance of answering questions.\n"
        prompt += "- Suggested Resources: Recommend resources relevant to the {question_set} question set.\n"
        prompt += "Use plain text, avoiding markdown tables and special characters like non-breaking hyphens; use regular hyphens (-) instead."
    else:
        prompt = f"Summarize the interview for a {role} in {mode} mode with {question_set} question set.\n"
        for i, (q, resp, fb) in enumerate(zip(questions, responses, feedbacks)):
            prompt += f"Question {i+1}: {q}\nResponse: {resp}\nFeedback: {fb}\n\n"
        prompt += "Generate a professional, human-readable summary in plain text. Include all questions asked and their responses. Format the output with the following sections, each starting on a new line with a clear header and using bullet points:\n"
        prompt += "- Questions and Responses: List each question, response, and feedback.\n"
        prompt += "- Areas of Strength: Highlight the candidate's strengths based on responses and feedback.\n"
        prompt += "- Areas to Improve: Suggest areas for improvement based on feedback.\n"
        prompt += "- Suggested Resources: Recommend resources relevant to the {question_set} question set.\n"
        prompt += "- Overall Score: Provide a final score out of 10 based on the responses and feedback.\n"
        prompt += "Use plain text, avoiding markdown tables and special characters like non-breaking hyphens; use regular hyphens (-) instead."
    
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are an interview summarizer. Format output as plain text for readability, using bullet points under clear section headers, avoiding markdown tables and special characters like non-breaking hyphens."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                max_completion_tokens=512,
                top_p=1,
                stream=False
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    raise Exception("Failed to generate summary after retries")