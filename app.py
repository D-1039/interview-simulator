import streamlit as st
import os
import json
import time
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
from fpdf import FPDF
import unicodedata

# Load environment variables
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")
try:
    client = Groq(api_key=api_key)
except Exception as e:
    raise RuntimeError(f"Failed to initialize Groq client: {e}")

# Bot functions (from bot.py)
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
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an interview question generator. Return questions in a numbered list format."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512,
                temperature=0.7
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
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an interview evaluator. Provide feedback in plain text, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512
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
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an interview summarizer. Format output as plain text with bullet points under headers, avoiding markdown tables."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=512
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            if "rate limit" in str(e).lower():
                time.sleep(2 ** attempt)
                continue
            raise e
    return "Error: Failed to generate summary after retries"

# Set page configuration
st.set_page_config(page_title="Interview Simulator", layout="wide")

# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = "selection"
if "role" not in st.session_state:
    st.session_state.role = None
if "domain" not in st.session_state:
    st.session_state.domain = None
if "mode" not in st.session_state:
    st.session_state.mode = None
if "question_set" not in st.session_state:
    st.session_state.question_set = "Standard"
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0
if "responses" not in st.session_state:
    st.session_state.responses = []
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = []
if "summary" not in st.session_state:
    st.session_state.summary = None
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "scores" not in st.session_state:
    st.session_state.scores = []
if "show_all_history" not in st.session_state:
    st.session_state.show_all_history = False

# File paths for history and leaderboard
HISTORY_FILE = "feedback_history.json"
LEADERBOARD_FILE = "leaderboard.json"

# Functions for history and leaderboard
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_leaderboard(leaderboard):
    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(leaderboard, f, indent=2)

# FPDF-based PDF generation
def normalize_text(text):
    if not text:
        return text
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

def generate_pdf_summary(user_id, role, mode, questions, responses, feedbacks, summary):
    try:
        user_id = normalize_text(user_id)
        role = normalize_text(role)
        mode = normalize_text(mode)
        questions = [normalize_text(q) for q in questions]
        responses = [normalize_text(r) for r in responses]
        feedbacks = [normalize_text(f) for f in feedbacks]
        summary = normalize_text(summary)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Interview Summary Report", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"User: {user_id} | Role: {role} | Mode: {mode}", ln=True, align="C")
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Questions and Responses", ln=True)
        pdf.set_font("Arial", "", 12)
        for i, (q, r, f) in enumerate(zip(questions, responses, feedbacks)):
            pdf.multi_cell(0, 10, f"Question {i+1}: {q}")
            pdf.multi_cell(0, 10, f"Response: {r}")
            pdf.multi_cell(0, 10, f"Feedback: {f}")
            pdf.ln(5)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Summary", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, summary)

        pdf_file = f"summary_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(pdf_file)
        return pdf_file if os.path.exists(pdf_file) else None
    except Exception as e:
        st.error(f"Failed to generate PDF: {str(e)}")
        return None

# Main UI
st.title("🚀 Interview Simulator Chatbot")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    user_id = st.text_input("User ID", value=st.session_state.user_id, key="user_id")
    role = st.selectbox("Job Role", ["Software Engineer", "Product Manager", "Data Analyst", "Other"], key="role")
    if role == "Other":
        role = st.text_input("Specify Job Role", key="custom_role")
    domain = st.text_input("Domain (optional, e.g., frontend, ML)", key="domain")
    mode = st.radio("Interview Mode", ["Technical Interview", "Behavioral Interview"], key="mode")
    question_set = st.selectbox("Question Set", ["Standard", "FAANG-style", "STAR-based"], key="question_set")
    num_questions = st.slider("Number of Questions", 1, 10, 5, key="num_questions")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Interview")
    if st.session_state.step == "selection":
        with st.container():
            st.info("Please select your settings and click 'Start Interview' below.")
            if st.button("Start Interview", key="start_interview", help="Begin the interview with the selected settings"):
                if not st.session_state.user_id:
                    st.warning("Please enter a User ID.")
                else:
                    try:
                        st.session_state.role = role
                        st.session_state.domain = domain
                        st.session_state.mode = mode
                        st.session_state.question_set = question_set
                        st.session_state.num_questions = num_questions
                        questions = generate_questions(role, domain, mode, num_questions, question_set)
                        if not questions:
                            st.error("Failed to generate questions. Please try again.")
                            st.session_state.step = "selection"
                        else:
                            st.session_state.questions = questions
                            st.session_state.current_question_index = 0
                            st.session_state.responses = []
                            st.session_state.feedbacks = []
                            st.session_state.scores = []
                            st.session_state.summary = None
                            st.session_state.step = "interview"
                    except Exception as e:
                        st.error(f"Error generating questions: {str(e)}")
                        st.session_state.step = "selection"
                    st.rerun()

    elif st.session_state.step == "interview":
        if not st.session_state.questions:
            st.error("No questions available. Returning to settings.")
            st.session_state.step = "selection"
            st.rerun()
        elif st.session_state.current_question_index >= len(st.session_state.questions):
            st.session_state.summary = generate_summary(
                st.session_state.role, st.session_state.mode, st.session_state.questions,
                st.session_state.responses, st.session_state.feedbacks, st.session_state.question_set
            )
            st.session_state.step = "summary"
            st.rerun()
        else:
            question = st.session_state.questions[st.session_state.current_question_index]
            with st.container():
                st.subheader(f"Question {st.session_state.current_question_index + 1}/{len(st.session_state.questions)}")
                st.write(question)

                if st.session_state.current_question_index > 0 and st.session_state.feedbacks:
                    with st.expander("Previous Feedback", expanded=False):
                        st.write(st.session_state.feedbacks[-1])

                answer = st.text_area("Your Answer", key=f"answer_{st.session_state.current_question_index}")

                col_submit, col_retry, col_skip = st.columns(3)
                with col_submit:
                    if st.button("Submit", key=f"submit_{st.session_state.current_question_index}"):
                        if answer:
                            feedback = evaluate_answer(question, answer, st.session_state.mode)
                            score = int(feedback.split("Score:")[1].split("/")[0].strip()) if "Score:" in feedback else 0
                            st.session_state.responses.append(answer)
                            st.session_state.feedbacks.append(feedback)
                            st.session_state.scores.append(score)

                            history = load_history()
                            if st.session_state.user_id not in history:
                                history[st.session_state.user_id] = []
                            history[st.session_state.user_id].append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "role": st.session_state.role,
                                "mode": st.session_state.mode,
                                "question_set": st.session_state.question_set,
                                "question": question,
                                "answer": answer,
                                "feedback": feedback,
                                "score": score
                            })
                            save_history(history)

                            leaderboard = load_leaderboard()
                            user_entry = next((entry for entry in leaderboard if entry["user_id"] == st.session_state.user_id), None)
                            if user_entry:
                                user_entry["total_score"] += score
                                user_entry["attempts"] += 1
                            else:
                                leaderboard.append({"user_id": st.session_state.user_id, "total_score": score, "attempts": 1})
                            save_leaderboard(leaderboard)

                            st.session_state.current_question_index += 1
                            if st.session_state.current_question_index >= len(st.session_state.questions):
                                st.session_state.summary = generate_summary(
                                    st.session_state.role, st.session_state.mode, st.session_state.questions,
                                    st.session_state.responses, st.session_state.feedbacks, st.session_state.question_set
                                )
                                st.session_state.step = "summary"
                            st.rerun()
                        else:
                            st.warning("Please provide an answer.")
                with col_retry:
                    if st.button("Retry", key=f"retry_{st.session_state.current_question_index}"):
                        st.rerun()
                with col_skip:
                    if st.button("Skip", key=f"skip_{st.session_state.current_question_index}"):
                        st.session_state.responses.append("Skipped")
                        st.session_state.feedbacks.append("No feedback for skipped question")
                        st.session_state.scores.append(0)
                        st.session_state.current_question_index += 1
                        if st.session_state.current_question_index >= len(st.session_state.questions):
                            st.session_state.summary = generate_summary(
                                st.session_state.role, st.session_state.mode, st.session_state.questions,
                                st.session_state.responses, st.session_state.feedbacks, st.session_state.question_set
                            )
                            st.session_state.step = "summary"
                        st.rerun()

    elif st.session_state.step == "summary":
        st.header("Interview Summary")
        with st.container():
            st.write(st.session_state.summary)

            col_txt, col_pdf, col_new = st.columns(3)
            with col_txt:
                if st.button("Export as TXT"):
                    with open("interview_summary.txt", "w", encoding="utf-8") as f:
                        f.write(st.session_state.summary)
                    with open("interview_summary.txt", "r", encoding="utf-8") as f:
                        st.download_button("Download TXT", f, file_name="interview_summary.txt")
            with col_pdf:
                if st.button("Export as PDF") and st.session_state.responses:
                    pdf_file = generate_pdf_summary(
                        st.session_state.user_id,
                        st.session_state.role,
                        st.session_state.mode,
                        st.session_state.questions,
                        st.session_state.responses,
                        st.session_state.feedbacks,
                        st.session_state.summary
                    )
                    if pdf_file and os.path.exists(pdf_file):
                        with open(pdf_file, "rb") as f:
                            st.download_button("Download PDF", f, file_name=pdf_file, mime="application/pdf")
                    else:
                        st.error("Failed to generate PDF. Please try again.")
            with col_new:
                if st.button("New Interview"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()

with col2:
    st.header("Feedback History")
    if st.session_state.user_id:
        history = load_history()
        if st.session_state.user_id in history:
            sorted_history = sorted(history[st.session_state.user_id], key=lambda x: x["timestamp"], reverse=True)
            display_limit = len(sorted_history) if st.session_state.show_all_history else min(5, len(sorted_history))
            for i, entry in enumerate(sorted_history[:display_limit]):
                with st.expander(f"{entry['timestamp']} - {entry['role']} ({entry['mode']})", expanded=False):
                    st.write(f"**Question**: {entry['question']}")
                    st.write(f"**Answer**: {entry['answer']}")
                    st.write(f"**Feedback**: {entry['feedback']}")
                    st.write(f"**Score**: {entry['score']}/10")
            if len(sorted_history) > 5 and not st.session_state.show_all_history:
                if st.button("Show More History", key="show_more_history"):
                    st.session_state.show_all_history = True
                    st.rerun()
            elif st.session_state.show_all_history and len(sorted_history) > 5:
                if st.button("Show Less History", key="show_less_history"):
                    st.session_state.show_all_history = False
                    st.rerun()

    st.header("Leaderboard")
    leaderboard = load_leaderboard()
    if leaderboard:
        leaderboard = sorted(leaderboard, key=lambda x: x["total_score"] / x["attempts"], reverse=True)
        for i, entry in enumerate(leaderboard[:5], 1):
            avg_score = entry["total_score"] / entry["attempts"]
            st.write(f"{i}. {entry['user_id']} - Avg Score: {avg_score:.2f} ({entry['attempts']} attempts)")

# Session management
with st.sidebar:
    st.header("Session Management")
    if st.button("Save Session"):
        session_data = {
            "user_id": st.session_state.user_id,
            "role": st.session_state.role,
            "domain": st.session_state.domain,
            "mode": st.session_state.mode,
            "question_set": st.session_state.question_set,
            "questions": st.session_state.questions,
            "responses": st.session_state.responses,
            "feedbacks": st.session_state.feedbacks,
            "summary": st.session_state.summary,
            "scores": st.session_state.scores,
            "show_all_history": st.session_state.show_all_history
        }
        with open("session.json", "w", encoding="utf-8") as f:
            json.dump(session_data, f)
        st.success("Session saved!")

    if st.button("Load Session"):
        if os.path.exists("session.json"):
            with open("session.json", "r", encoding="utf-8") as f:
                session_data = json.load(f)
            st.session_state.user_id = session_data["user_id"]
            st.session_state.role = session_data["role"]
            st.session_state.domain = session_data["domain"]
            st.session_state.mode = session_data["mode"]
            st.session_state.question_set = session_data["question_set"]
            st.session_state.questions = session_data["questions"]
            st.session_state.responses = session_data["responses"]
            st.session_state.feedbacks = session_data["feedbacks"]
            st.session_state.summary = session_data["summary"]
            st.session_state.scores = session_data["scores"]
            st.session_state.show_all_history = session_data.get("show_all_history", False)
            st.session_state.step = "summary"
            st.rerun()
        else:
            st.warning("No saved session found.")