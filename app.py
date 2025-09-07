import streamlit as st
from bot import generate_questions, evaluate_answer, generate_summary
import os
import json
from datetime import datetime
from fpdf import FPDF
import unicodedata

# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = "settings"
    st.session_state.questions = []
    st.session_state.current_question_index = 0
    st.session_state.responses = []
    st.session_state.feedbacks = []
    st.session_state.role = ""
    st.session_state.domain = ""
    st.session_state.mode = ""
    st.session_state.num_questions = 5
    st.session_state.question_set = "Standard"

# Settings step
if st.session_state.step == "settings":
    st.title("🚀 Interview Simulator Chatbot")
    user_id = st.text_input("User ID", key="user_id")
    role = st.selectbox("Job Role", ["Software Engineer", "Data Scientist", "Product Manager"], key="role")
    domain = st.text_input("Domain (optional)", key="domain")
    mode = st.radio("Interview Mode", ["Technical Interview", "Behavioral Interview"], key="mode")
    num_questions = st.slider("Number of Questions", 1, 10, 5, key="num_questions")
    question_set = st.selectbox("Question Set", ["Standard", "FAANG-style"], key="question_set")
    if st.button("Start Interview"):
        if not user_id:
            st.error("Please enter a User ID")
        else:
            st.session_state.user_id = user_id
            st.session_state.role = role
            st.session_state.domain = domain
            st.session_state.mode = mode
            st.session_state.num_questions = num_questions
            st.session_state.question_set = question_set
            try:
                st.session_state.questions = generate_questions(role, domain, mode, num_questions, question_set)
                if not st.session_state.questions:
                    st.error("Failed to generate questions. Please try again.")
                    st.session_state.step = "settings"
                else:
                    st.session_state.current_question_index = 0
                    st.session_state.responses = []
                    st.session_state.feedbacks = []
                    st.session_state.step = "interview"
            except Exception as e:
                st.error(f"Error generating questions: {e}")
                st.session_state.step = "settings"
            st.rerun()

# Interview step
elif st.session_state.step == "interview":
    if not st.session_state.questions:
        st.error("No questions available. Returning to settings.")
        st.session_state.step = "settings"
        st.rerun()
    elif st.session_state.current_question_index >= len(st.session_state.questions):
        st.session_state.step = "summary"
        st.rerun()
    else:
        question = st.session_state.questions[st.session_state.current_question_index]
        with st.container():
            st.subheader(f"Question {st.session_state.current_question_index + 1}")
            st.write(question)
            answer = st.text_area("Your Answer", key=f"answer_{st.session_state.current_question_index}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Submit Answer"):
                    if answer.strip():
                        feedback = evaluate_answer(question, answer, st.session_state.mode)
                        st.session_state.responses.append(answer)
                        st.session_state.feedbacks.append(feedback)
                        st.session_state.current_question_index += 1
                    else:
                        st.error("Please provide an answer before submitting.")
                    st.rerun()
            with col2:
                if st.button("Skip Question"):
                    st.session_state.responses.append("Skipped")
                    st.session_state.feedbacks.append("No feedback for skipped question")
                    st.session_state.current_question_index += 1
                    st.rerun()

# ... rest of app.py (summary, history, leaderboard, etc.) ...