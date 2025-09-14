import streamlit as st
import os
import json
from datetime import datetime
import sqlite3
from fpdf import FPDF
import unicodedata
from bot import init_db, generate_questions, evaluate_answer, generate_summary

# Set page configuration
st.set_page_config(page_title="Interview Simulator", layout="wide")
st.markdown("""
<style>
    @media (max-width: 600px) { 
        .stButton button { width: 100%; } 
        .stTextInput { width: 100%; }
    }
    .stTextArea, .stTextInput, .stSelectbox, .stRadio, .stSlider { 
        max-width: 600px; 
    }
</style>
""", unsafe_allow_html=True)

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
if "difficulty" not in st.session_state:
    st.session_state.difficulty = "Medium"
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0
if "responses" not in st.session_state:
    st.session_state.responses = []
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = []
if "scores" not in st.session_state:
    st.session_state.scores = []
if "summary" not in st.session_state:
    st.session_state.summary = None
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "show_all_history" not in st.session_state:
    st.session_state.show_all_history = False
if "timer" not in st.session_state:
    st.session_state.timer = 300  # 5 minutes per question

# Initialize database
init_db()

# Functions for history and leaderboard
def load_history(user_id):
    conn = sqlite3.connect("interview.db")
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    history = [
        {
            "timestamp": row[1],
            "role": row[2],
            "mode": row[3],
            "question_set": row[4],
            "question": row[5],
            "answer": row[6],
            "feedback": row[7],
            "score": row[8]
        } for row in c.fetchall()
    ]
    conn.close()
    return history

def save_history(user_id, entry):
    conn = sqlite3.connect("interview.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (user_id, timestamp, role, mode, question_set, question, answer, feedback, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            entry["timestamp"],
            entry["role"],
            entry["mode"],
            entry["question_set"],
            entry["question"],
            entry["answer"],
            entry["feedback"],
            entry["score"]
        )
    )
    conn.commit()
    conn.close()

def load_leaderboard():
    conn = sqlite3.connect("interview.db")
    c = conn.cursor()
    c.execute("SELECT user_id, total_score, attempts FROM leaderboard")
    leaderboard = [
        {"user_id": row[0], "total_score": row[1], "attempts": row[2]}
        for row in c.fetchall()
    ]
    conn.close()
    return leaderboard

def save_leaderboard(user_id, score):
    conn = sqlite3.connect("interview.db")
    c = conn.cursor()
    c.execute("SELECT total_score, attempts FROM leaderboard WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        total_score, attempts = result
        c.execute(
            "UPDATE leaderboard SET total_score = ?, attempts = ? WHERE user_id = ?",
            (total_score + score, attempts + 1, user_id)
        )
    else:
        c.execute(
            "INSERT INTO leaderboard (user_id, total_score, attempts) VALUES (?, ?, ?)",
            (user_id, score, 1)
        )
    conn.commit()
    conn.close()

# PDF generation
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

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    user_id = st.text_input("User ID", value=st.session_state.user_id, help="Enter a unique user ID")
    if user_id:
        st.session_state.user_id = user_id

    role = st.selectbox("Job Role", ["Software Engineer", "Product Manager", "Data Analyst", "Other"], help="Select or specify your job role")
    if role == "Other":
        role = st.text_input("Specify Job Role", help="Enter a custom job role (1-100 characters)")
    domain = st.text_input("Domain (optional, e.g., frontend, ML)", help="Specify a domain (up to 100 characters)")
    mode = st.radio("Interview Mode", ["Technical Interview", "Behavioral Interview"], help="Choose interview type")
    question_set = st.selectbox("Question Set", ["Standard", "FAANG-style", "STAR-based"], help="Select question style")
    difficulty = st.selectbox("Difficulty", ["Beginner", "Medium", "Advanced"], help="Select question difficulty")
    num_questions = st.slider("Number of Questions", 1, 10, 5, help="Choose number of questions (1-10)")

# Timer update
if st.session_state.step == "interview" and st.session_state.timer > 0:
    st.session_state.timer -= 1
    if st.session_state.timer <= 0:
        st.warning("Time's up for this question!")
        st.session_state.responses.append("Skipped")
        st.session_state.feedbacks.append("Skipped due to time limit")
        st.session_state.scores.append(0)
        st.session_state.current_question_index += 1
        st.session_state.timer = 300
        if st.session_state.current_question_index >= len(st.session_state.questions):
            with st.spinner("Generating summary, please wait..."):
                st.session_state.summary = generate_summary(
                    st.session_state.role, st.session_state.mode, st.session_state.questions,
                    st.session_state.responses, st.session_state.feedbacks,
                    st.session_state.question_set, st.session_state.difficulty
                )
            st.session_state.step = "summary"
        st.rerun()

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Interview")
    if st.session_state.step == "selection":
        with st.container():
            st.info("Select your settings and click 'Start Interview' below.")
            if st.button("Start Interview", key="start_interview", help="Begin the interview", args={"aria-label": "Start Interview"}):
                if not user_id:
                    st.warning("Please enter a User ID.")
                elif not role.strip() or len(role) > 100:
                    st.warning("Please provide a valid job role (1-100 characters).")
                elif domain and len(domain) > 100:
                    st.warning("Domain must be 1-100 characters.")
                else:
                    st.session_state.role = role
                    st.session_state.domain = domain
                    st.session_state.mode = mode
                    st.session_state.question_set = question_set
                    st.session_state.difficulty = difficulty
                    with st.spinner("Generating questions, please wait..."):
                        try:
                            st.session_state.questions = generate_questions(role, domain, mode, num_questions, question_set, difficulty)
                            if len(st.session_state.questions) != num_questions:
                                st.warning(f"Generated {len(st.session_state.questions)} questions instead of {num_questions}. Please try again.")
                                st.session_state.questions = []
                            else:
                                st.session_state.current_question_index = 0
                                st.session_state.responses = []
                                st.session_state.feedbacks = []
                                st.session_state.scores = []
                                st.session_state.step = "interview"
                                st.session_state.timer = 300
                                st.rerun()
                        except Exception as e:
                            st.error(f"Failed to generate questions: {str(e)}. Check your HF_TOKEN setup.")
    
    elif st.session_state.step == "interview" and st.session_state.questions:
        question = st.session_state.questions[st.session_state.current_question_index]
        with st.container():
            st.subheader(f"Question {st.session_state.current_question_index + 1}/{len(st.session_state.questions)}")
            st.write(f"Time remaining: {st.session_state.timer//60}:{st.session_state.timer%60:02d}")
            st.write(question)
            
            if st.session_state.current_question_index > 0 and st.session_state.feedbacks:
                with st.expander("Previous Feedback", expanded=False):
                    st.write(st.session_state.feedbacks[-1])
            
            answer = st.text_area("Your Answer", key=f"answer_{st.session_state.current_question_index}", help="Enter your response here")
            if answer:
                st.write(f"Word count: {len(answer.split())}")
            
            col_submit, col_retry, col_skip = st.columns(3)
            with col_submit:
                if st.button("Submit", key=f"submit_{st.session_state.current_question_index}", help="Submit your answer", args={"aria-label": "Submit Answer"}):
                    if answer:
                        with st.spinner("Evaluating answer, please wait..."):
                            try:
                                feedback, score = evaluate_answer(question, answer, st.session_state.mode)
                                st.session_state.responses.append(answer)
                                st.session_state.feedbacks.append(feedback)
                                st.session_state.scores.append(score)

                                history_entry = {
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "role": role,
                                    "mode": mode,
                                    "question_set": question_set,
                                    "question": question,
                                    "answer": answer,
                                    "feedback": feedback,
                                    "score": score
                                }
                                save_history(user_id, history_entry)
                                save_leaderboard(user_id, score)

                                st.session_state.current_question_index += 1
                                st.session_state.timer = 300
                                if st.session_state.current_question_index >= len(st.session_state.questions):
                                    with st.spinner("Generating summary, please wait..."):
                                        st.session_state.summary = generate_summary(
                                            role, mode, st.session_state.questions, st.session_state.responses,
                                            st.session_state.feedbacks, question_set, difficulty
                                        )
                                    st.session_state.step = "summary"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to evaluate answer: {str(e)}. Check your HF_TOKEN setup.")
                    else:
                        st.warning("Please provide an answer.")
            with col_retry:
                if st.button("Retry", key=f"retry_{st.session_state.current_question_index}", help="Retry this question", args={"aria-label": "Retry Question"}):
                    st.session_state.timer = 300
                    st.rerun()
            with col_skip:
                if st.button("Skip", key=f"skip_{st.session_state.current_question_index}", help="Skip this question", args={"aria-label": "Skip Question"}):
                    st.session_state.responses.append("Skipped")
                    st.session_state.feedbacks.append("Skipped by user")
                    st.session_state.scores.append(0)
                    st.session_state.current_question_index += 1
                    st.session_state.timer = 300
                    if st.session_state.current_question_index >= len(st.session_state.questions):
                        with st.spinner("Generating summary, please wait..."):
                            st.session_state.summary = generate_summary(
                                role, mode, st.session_state.questions, st.session_state.responses,
                                st.session_state.feedbacks, question_set, difficulty
                            )
                        st.session_state.step = "summary"
                    st.rerun()

    elif st.session_state.step == "summary":
        st.header("Interview Summary")
        with st.container():
            st.write(st.session_state.summary)
            
            if st.session_state.scores:
                st.subheader("Your Performance")
                chart_data = {
                    "type": "bar",
                    "data": {
                        "labels": [f"Q{i+1}" for i in range(len(st.session_state.scores))],
                        "datasets": [{
                            "label": "Score",
                            "data": st.session_state.scores,
                            "backgroundColor": "rgba(75, 192, 192, 0.5)",
                            "borderColor": "rgba(75, 192, 192, 1)",
                            "borderWidth": 1
                        }]
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "beginAtZero": True,
                                "max": 10
                            }
                        }
                    }
                }
                # Render Chart.js using st.markdown with HTML/JS
                chart_html = f"""
                <div>
                    <canvas id="performanceChart"></canvas>
                    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                    <script>
                        const ctx = document.getElementById('performanceChart').getContext('2d');
                        new Chart(ctx, {json.dumps(chart_data)});
                    </script>
                </div>
                """
                st.markdown(chart_html, unsafe_allow_html=True)

            col_txt, col_pdf, col_new = st.columns(3)
            with col_txt:
                if st.button("Export as TXT", help="Download summary as text", args={"aria-label": "Export as TXT"}):
                    with open("interview_summary.txt", "w", encoding="utf-8") as f:
                        f.write(st.session_state.summary)
                    with open("interview_summary.txt", "r", encoding="utf-8") as f:
                        st.download_button("Download TXT", f, file_name="interview_summary.txt")
                    st.success("TXT file generated successfully!")
            with col_pdf:
                if st.button("Export as PDF", disabled=not st.session_state.responses, help="Download summary as PDF", args={"aria-label": "Export as PDF"}):
                    with st.spinner("Generating PDF, please wait..."):
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
                            st.success("PDF generated successfully!")
                        else:
                            st.error("Failed to generate PDF. Please try again.")
            with col_new:
                if st.button("New Interview", help="Start a new interview", args={"aria-label": "New Interview"}):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()

with col2:
    st.header("Feedback History")
    if st.session_state.user_id:
        history = load_history(st.session_state.user_id)
        display_limit = len(history) if st.session_state.show_all_history else min(5, len(history))
        for i, entry in enumerate(history[:display_limit]):
            with st.expander(f"{entry['timestamp']} - {entry['role']} ({entry['mode']})", expanded=False):
                st.write(f"**Question**: {entry['question']}")
                st.write(f"**Answer**: {entry['answer']}")
                st.write(f"**Feedback**: {entry['feedback']}")
                st.write(f"**Score**: {entry['score']}/10")
        if len(history) > 5 and not st.session_state.show_all_history:
            if st.button("Show More History", key="show_more_history", help="View more history", args={"aria-label": "Show More History"}):
                st.session_state.show_all_history = True
                st.rerun()
        elif st.session_state.show_all_history and len(history) > 5:
            if st.button("Show Less History", key="show_less_history", help="View less history", args={"aria-label": "Show Less History"}):
                st.session_state.show_all_history = False
                st.rerun()

    st.header("Leaderboard")
    leaderboard = load_leaderboard()
    if leaderboard:
        leaderboard = sorted(leaderboard, key=lambda x: x["total_score"] / x["attempts"], reverse=True)
        for i, entry in enumerate(leaderboard[:5], 1):
            avg_score = entry["total_score"] / entry["attempts"]
            st.write(f"{i}. {entry['user_id']} - Avg Score: {avg_score:.2f} ({entry['attempts']} attempts)")

# Session Management
with st.sidebar:
    st.header("Session Management")
    if st.button("Save Session", help="Save current session", args={"aria-label": "Save Session"}):
        session_data = {
            "user_id": st.session_state.user_id,
            "role": st.session_state.role,
            "domain": st.session_state.domain,
            "mode": st.session_state.mode,
            "question_set": st.session_state.question_set,
            "difficulty": st.session_state.difficulty,
            "questions": st.session_state.questions,
            "responses": st.session_state.responses,
            "feedbacks": st.session_state.feedbacks,
            "summary": st.session_state.summary,
            "scores": st.session_state.scores,
            "show_all_history": st.session_state.show_all_history
        }
        session_file = f"session_{st.session_state.user_id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f)
        st.success("Session saved successfully!")

    if st.button("Load Session", help="Load previous session", args={"aria-label": "Load Session"}):
        session_file = f"session_{st.session_state.user_id}.json"
        if os.path.exists(session_file):
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            st.session_state.user_id = session_data["user_id"]
            st.session_state.role = session_data["role"]
            st.session_state.domain = session_data["domain"]
            st.session_state.mode = session_data["mode"]
            st.session_state.question_set = session_data["question_set"]
            st.session_state.difficulty = session_data.get("difficulty", "Medium")
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