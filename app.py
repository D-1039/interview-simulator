import streamlit as st
import os
import json
from datetime import datetime
from bot import generate_questions, evaluate_answer, generate_summary
from fpdf import FPDF
import unicodedata

# Set page configuration for a clean, professional look
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
    """Normalize Unicode characters to ASCII for FPDF compatibility."""
    if not text:
        return text
    # Normalize to NFKD form and encode to ASCII, replacing non-ASCII characters
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

def generate_pdf_summary(user_id, role, mode, questions, responses, feedbacks, summary):
    try:
        # Normalize text to handle Unicode characters
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

        # Add summary with bullet points
        pdf.set_font("Arial", "B", 14)
        lines = summary.split("\n")
        for line in lines:
            if line.strip().startswith("- "):
                pdf.set_font("Arial", "", 12)
                pdf.multi_cell(0, 10, f"  - {line.strip()[2:]}")
            elif line.strip():
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, line.strip(), ln=True)
                pdf.ln(2)

        pdf_file = f"summary_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(pdf_file)
        return pdf_file if os.path.exists(pdf_file) else None
    except Exception as e:
        st.error(f"Failed to generate PDF: {str(e)}")
        return None

# Main UI
st.title("🚀 Interview Simulator Chatbot")

# Sidebar for settings (without Start Interview button)
with st.sidebar:
    st.header("Settings")
    user_id = st.text_input("User ID", value=st.session_state.user_id)
    if user_id:
        st.session_state.user_id = user_id

    role = st.selectbox("Job Role", ["Software Engineer", "Product Manager", "Data Analyst", "Other"])
    if role == "Other":
        role = st.text_input("Specify Job Role")
    domain = st.text_input("Domain (optional, e.g., frontend, ML)")
    mode = st.radio("Interview Mode", ["Technical Interview", "Behavioral Interview"])
    question_set = st.selectbox("Question Set", ["Standard", "FAANG-style", "STAR-based"])
    num_questions = st.slider("Number of Questions", 1, 10, 5)

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Interview")
    if st.session_state.step == "selection":
        with st.container():
            st.info("Please select your settings and click 'Start Interview' below.")
            if st.button("Start Interview", key="start_interview", help="Begin the interview with the selected settings"):
                if not user_id:
                    st.warning("Please enter a User ID.")
                else:
                    st.session_state.role = role
                    st.session_state.domain = domain
                    st.session_state.mode = mode
                    st.session_state.question_set = question_set
                    try:
                        st.session_state.questions = generate_questions(role, domain, mode, num_questions, question_set)
                        if len(st.session_state.questions) != num_questions:
                            st.warning(f"Generated {len(st.session_state.questions)} questions instead of {num_questions}. Please try again.")
                            st.session_state.questions = []
                        else:
                            st.session_state.current_question_index = 0
                            st.session_state.responses = []
                            st.session_state.feedbacks = []
                            st.session_state.scores = []
                            st.session_state.step = "interview"
                            st.session_state.summary = None
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to generate questions: {str(e)}")
    
    elif st.session_state.step == "interview" and st.session_state.questions:
        question = st.session_state.questions[st.session_state.current_question_index]
        with st.container():
            st.subheader(f"Question {st.session_state.current_question_index + 1}/{len(st.session_state.questions)}")
            st.write(question)
            
            # Display previous feedback if available
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

                        # Save to history
                        history = load_history()
                        if user_id not in history:
                            history[user_id] = []
                        history[user_id].append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "role": role,
                            "mode": mode,
                            "question_set": question_set,
                            "question": question,
                            "answer": answer,
                            "feedback": feedback,
                            "score": score
                        })
                        save_history(history)

                        # Update leaderboard
                        leaderboard = load_leaderboard()
                        user_entry = next((entry for entry in leaderboard if entry["user_id"] == user_id), None)
                        if user_entry:
                            user_entry["total_score"] += score
                            user_entry["attempts"] += 1
                        else:
                            leaderboard.append({"user_id": user_id, "total_score": score, "attempts": 1})
                        save_leaderboard(leaderboard)

                        st.session_state.current_question_index += 1
                        if st.session_state.current_question_index >= len(st.session_state.questions):
                            st.session_state.summary = generate_summary(
                                role, mode, st.session_state.questions, st.session_state.responses,
                                st.session_state.feedbacks, question_set
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
                    st.session_state.current_question_index += 1
                    if st.session_state.current_question_index >= len(st.session_state.questions):
                        st.session_state.summary = generate_summary(
                            role, mode, st.session_state.questions, st.session_state.responses,
                            st.session_state.feedbacks, question_set
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
                if st.button("Export as PDF", disabled=not st.session_state.responses):
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
            # Sort history by timestamp in descending order (newest first)
            sorted_history = sorted(history[st.session_state.user_id], key=lambda x: x["timestamp"], reverse=True)
            # Show only the first 5 entries unless "Show More History" is clicked
            display_limit = len(sorted_history) if st.session_state.show_all_history else min(5, len(sorted_history))
            for i, entry in enumerate(sorted_history[:display_limit]):
                with st.expander(f"{entry['timestamp']} - {entry['role']} ({entry['mode']})", expanded=False):
                    st.write(f"**Question**: {entry['question']}")
                    st.write(f"**Answer**: {entry['answer']}")
                    st.write(f"**Feedback**: {entry['feedback']}")
                    st.write(f"**Score**: {entry['score']}/10")
            # Add "Show More History" button if there are more than 5 entries
            if len(sorted_history) > 5 and not st.session_state.show_all_history:
                if st.button("Show More History", key="show_more_history"):
                    st.session_state.show_all_history = True
                    st.rerun()
            # Add "Show Less History" button if showing all entries
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

# Save and load session
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