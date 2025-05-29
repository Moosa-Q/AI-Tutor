import streamlit as st
import openai
import json
import hashlib
import re
import sqlite3
import bcrypt
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="AI Coding Tutor",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Database initialization
def init_database():
    """Initialize SQLite database with secure practices"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Create users table with proper constraints
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Create user progress table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            quiz_score INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password_secure(password):
    """Secure password hashing using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def create_user(email, password, age):
    """Create new user with parameterized queries"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # Use parameterized query to prevent SQL injection
        hashed_password = hash_password_secure(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, age) VALUES (?, ?, ?)",
            (email, hashed_password, age)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None  # User already exists
    finally:
        conn.close()

def authenticate_user(email, password):
    """Authenticate user with secure practices"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # Use parameterized query
        cursor.execute(
            "SELECT id, password_hash, age FROM users WHERE email = ?",
            (email,)
        )
        result = cursor.fetchone()
        
        if result and verify_password(password, result[1]):
            # Update last login
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (result[0],)
            )
            conn.commit()
            return {
                'id': result[0],
                'email': email,
                'age': result[2]
            }
        return None
    finally:
        conn.close()

def save_user_progress(user_id, topic, score):
    """Save user quiz progress"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO user_progress (user_id, topic, quiz_score) VALUES (?, ?, ?)",
            (user_id, topic, score)
        )
        conn.commit()
    finally:
        conn.close()

def get_user_progress(user_id):
    """Get user's learning progress"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT topic, quiz_score, completed_at FROM user_progress WHERE user_id = ? ORDER BY completed_at DESC",
            (user_id,)
        )
        return cursor.fetchall()
    finally:
        conn.close()

# Custom CSS for styling (same as before)
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .lesson-container {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
    }
    
    .quiz-container {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
    }
    
    .question-box {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border: 2px solid #ddd;
        color: #333;
    }
    
    .success-box {
        background: linear-gradient(90deg, #00b894 0%, #00cec9 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: linear-gradient(90deg, #fdcb6e 0%, #e17055 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 25px;
        font-weight: bold;
    }
    
    .login-container {
        background: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        max-width: 500px;
        margin: 2rem auto;
    }
    
    .progress-container {
        background: #f1f3f4;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'current_lesson' not in st.session_state:
    st.session_state.current_lesson = None
if 'quiz_questions' not in st.session_state:
    st.session_state.quiz_questions = []
if 'quiz_answers' not in st.session_state:
    st.session_state.quiz_answers = {}
if 'quiz_submitted' not in st.session_state:
    st.session_state.quiz_submitted = False
if 'lesson_topic' not in st.session_state:
    st.session_state.lesson_topic = ""

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def login_page():
    """Display login page with registration"""
    st.markdown('<div class="main-header"><h1>🚀 AI Coding Tutor</h1><p>Master Programming with Personalized AI Lessons</p></div>', unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            
            # Toggle between login and registration
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                st.markdown("### Welcome Back!")
                with st.form("login_form"):
                    email = st.text_input("📧 Email Address", placeholder="your.email@example.com")
                    password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
                    
                    submit = st.form_submit_button("🚀 Login", use_container_width=True)
                    
                    if submit:
                        if not email or not password:
                            st.error("Please fill in all fields!")
                        elif not validate_email(email):
                            st.error("Please enter a valid email address!")
                        else:
                            user = authenticate_user(email, password)
                            if user:
                                st.session_state.logged_in = True
                                st.session_state.user_data = user
                                st.success("Login successful! 🎉")
                                st.rerun()
                            else:
                                st.error("Invalid email or password!")
            
            with tab2:
                st.markdown("### Create Account")
                with st.form("register_form"):
                    reg_email = st.text_input("📧 Email Address", placeholder="your.email@example.com", key="reg_email")
                    reg_password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="reg_password")
                    confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Confirm your password")
                    age = st.number_input("🎂 Age", min_value=8, max_value=100, value=18)
                    
                    register = st.form_submit_button("📝 Create Account", use_container_width=True)
                    
                    if register:
                        if not reg_email or not reg_password or not confirm_password:
                            st.error("Please fill in all fields!")
                        elif not validate_email(reg_email):
                            st.error("Please enter a valid email address!")
                        elif len(reg_password) < 6:
                            st.error("Password must be at least 6 characters long!")
                        elif reg_password != confirm_password:
                            st.error("Passwords don't match!")
                        else:
                            user_id = create_user(reg_email, reg_password, age)
                            if user_id:
                                st.success("Account created successfully! Please login.")
                            else:
                                st.error("Email already exists! Please use a different email.")
            
            st.markdown('</div>', unsafe_allow_html=True)

def display_user_progress():
    """Display user's learning progress"""
    if 'id' in st.session_state.user_data:
        progress = get_user_progress(st.session_state.user_data['id'])
        
        if progress:
            st.markdown('<div class="progress-container">', unsafe_allow_html=True)
            st.markdown("### 📊 Your Learning Progress")
            
            for topic, score, completed_at in progress[:5]:  # Show last 5
                score_color = "🟢" if score >= 5 else "🟡"
                st.markdown(f"{score_color} **{topic}** - Score: {score}/8 - {completed_at}")
            
            st.markdown('</div>', unsafe_allow_html=True)

def get_age_appropriate_tone(age):
    """Get age-appropriate communication tone"""
    if age < 13:
        return "friendly, simple, and encouraging like talking to a curious kid"
    elif age < 18:
        return "engaging and supportive like talking to a teenager"
    elif age < 25:
        return "enthusiastic and relatable like talking to a young adult"
    else:
        return "professional but approachable like talking to an adult professional"

def generate_lesson(topic, age):
    """Generate AI lesson content"""
    tone = get_age_appropriate_tone(age)
    
    prompt = f"""
    Create a comprehensive coding lesson about "{topic}" for someone who is {age} years old.
    
    Use a {tone} tone throughout the lesson.
    
    Structure the lesson as follows:
    1. Introduction - What is this topic and why is it important?
    2. Core Concepts - Break down the main ideas
    3. Practical Examples - Show real code examples with explanations
    4. Common Use Cases - Where and when to use this
    5. Best Practices - Tips for writing good code
    6. Next Steps - What to learn after mastering this
    
    Make sure the content is detailed enough that someone could understand the topic VERY well just from this lesson.
    Include code examples where relevant and explain them thoroughly.
    
    Keep the explanation comprehensive but digestible, appropriate for age {age}.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating lesson: {str(e)}"

def generate_quiz(topic, age):
    """Generate quiz questions"""
    tone = get_age_appropriate_tone(age)
    
    prompt = f"""
    Create exactly 8 multiple choice quiz questions about "{topic}" for someone who is {age} years old.
    
    Use a {tone} tone for the questions.
    
    Each question should test understanding of the key concepts from the lesson.
    Make them challenging but fair - someone who studied the lesson should be able to answer them.
    
    Format as JSON with this exact structure:
    {{
        "questions": [
            {{
                "question": "Question text here?",
                "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                "correct": 0,
                "explanation": "Why this answer is correct"
            }}
        ]
    }}
    
    The "correct" field should be the index (0-3) of the correct answer.
    Make sure all 8 questions are different and cover various aspects of the topic.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.7
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response if it's wrapped in markdown
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        
        quiz_data = json.loads(response_text)
        return quiz_data["questions"]
    except json.JSONDecodeError as e:
        st.error(f"Error parsing quiz JSON: {str(e)}")
        st.error(f"Raw response: {response_text[:200]}...")
        return []
    except Exception as e:
        st.error(f"Error generating quiz: {str(e)}")
        return []

def answer_question(question, lesson_topic, age):
    """Answer user questions about the lesson"""
    tone = get_age_appropriate_tone(age)
    
    prompt = f"""
    You are helping someone who is {age} years old learn about "{lesson_topic}".
    
    They asked: "{question}"
    
    Provide a helpful, clear answer using a {tone} tone.
    If the question is related to the lesson topic, give a thorough explanation.
    If it's not related, gently redirect them back to the lesson topic.
    
    Keep your answer focused and educational.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Sorry, I couldn't process your question right now. Error: {str(e)}"

def topic_selection_page():
    """Display topic selection page"""
    st.markdown('<div class="main-header"><h1>🎯 Choose Your Learning Path</h1><p>Select what you\'d like to master today!</p></div>', unsafe_allow_html=True)
    
    # Display user progress
    display_user_progress()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💻 Programming Languages")
        languages = [
            "Python Basics", "JavaScript Fundamentals", "Java Essentials", 
            "C++ Programming", "HTML & CSS", "SQL Database Queries",
            "React Framework", "Node.js Backend", "Python Data Science"
        ]
        
        for lang in languages:
            if st.button(lang, key=f"lang_{lang}", use_container_width=True):
                start_lesson(lang)
    
    with col2:
        st.markdown("### 🎯 Job Roles & Certifications")
        roles = [
            "Web Developer Skills", "Data Scientist Path", "DevOps Engineer", 
            "Cybersecurity Analyst", "Mobile App Developer", "Cloud Engineer AWS",
            "Machine Learning Engineer", "Full Stack Developer", "Database Administrator"
        ]
        
        for role in roles:
            if st.button(role, key=f"role_{role}", use_container_width=True):
                start_lesson(role)
    
    st.markdown("---")
    st.markdown("### 🔧 Custom Topic")
    custom_topic = st.text_input("Enter any programming topic you'd like to learn:")
    if st.button("Start Custom Lesson") and custom_topic:
        start_lesson(custom_topic)

def start_lesson(topic):
    """Start a new lesson"""
    st.session_state.lesson_topic = topic
    st.session_state.current_lesson = None
    st.session_state.quiz_questions = []
    st.session_state.quiz_answers = {}
    st.session_state.quiz_submitted = False
    
    with st.spinner(f"🧠 Generating your personalized lesson on {topic}..."):
        lesson_content = generate_lesson(topic, st.session_state.user_data['age'])
        st.session_state.current_lesson = lesson_content
    
    st.rerun()

def lesson_page():
    """Display lesson content and interactions"""
    if not st.session_state.current_lesson:
        topic_selection_page()
        return
    
    st.markdown(f'<div class="main-header"><h1>📚 Learning: {st.session_state.lesson_topic}</h1></div>', unsafe_allow_html=True)
    
    # Lesson content
    st.markdown('<div class="lesson-container">', unsafe_allow_html=True)
    st.markdown("## 📖 Your Lesson")
    st.markdown(st.session_state.current_lesson)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Question section
    st.markdown("---")
    st.markdown("## 💭 Ask Questions About This Lesson")
    
    with st.form("question_form"):
        user_question = st.text_area("What would you like to know more about?", 
                                   placeholder="Ask anything about the lesson...")
        ask_button = st.form_submit_button("🤔 Get Answer")
        
        if ask_button and user_question:
            with st.spinner("🤖 Thinking..."):
                answer = answer_question(user_question, st.session_state.lesson_topic, 
                                       st.session_state.user_data['age'])
            st.markdown(f"**🤖 AI Tutor:** {answer}")
    
    # Quiz section
    st.markdown("---")
    if not st.session_state.quiz_questions:
        if st.button("📝 Take Quiz to Continue", use_container_width=True):
            with st.spinner("📝 Generating your quiz..."):
                st.session_state.quiz_questions = generate_quiz(st.session_state.lesson_topic, 
                                                               st.session_state.user_data['age'])
            st.rerun()
    else:
        display_quiz()
    
    # Navigation
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Choose New Topic"):
            st.session_state.current_lesson = None
            st.session_state.lesson_topic = ""
            st.rerun()
    
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.user_data = {}
            st.rerun()

def display_quiz():
    """Display quiz questions"""
    st.markdown('<div class="quiz-container">', unsafe_allow_html=True)
    st.markdown("## 🎯 Master Your Knowledge Quiz")
    st.markdown("**You need 5 correct answers out of 8 to pass!**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if not st.session_state.quiz_submitted:
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz_questions):
                st.markdown(f'<div class="question-box">', unsafe_allow_html=True)
                st.markdown(f"**Question {i+1}:** {q['question']}")
                
                answer = st.radio(
                    f"Select your answer for question {i+1}:",
                    q['options'],
                    key=f"q_{i}",
                    label_visibility="collapsed"
                )
                st.session_state.quiz_answers[i] = answer
                st.markdown('</div>', unsafe_allow_html=True)
            
            submit_quiz = st.form_submit_button("🎯 Submit Quiz", use_container_width=True)
            
            if submit_quiz:
                st.session_state.quiz_submitted = True
                st.rerun()
    
    else:
        # Show results
        correct_count = 0
        for i, q in enumerate(st.session_state.quiz_questions):
            user_answer = st.session_state.quiz_answers.get(i, "")
            correct_option = q['options'][q['correct']]
            
            st.markdown(f'<div class="question-box">', unsafe_allow_html=True)
            st.markdown(f"**Question {i+1}:** {q['question']}")
            
            if user_answer == correct_option:
                st.markdown(f"✅ **Your answer:** {user_answer} - **Correct!**")
                correct_count += 1
            else:
                st.markdown(f"❌ **Your answer:** {user_answer}")
                st.markdown(f"✅ **Correct answer:** {correct_option}")
            
            st.markdown(f"**Explanation:** {q['explanation']}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Save progress to database
        if 'id' in st.session_state.user_data:
            save_user_progress(st.session_state.user_data['id'], st.session_state.lesson_topic, correct_count)
        
        # Final result
        if correct_count >= 5:
            st.markdown(f'<div class="success-box"><h3>🎉 Congratulations!</h3><p>You scored {correct_count}/8 - You\'ve mastered this topic!</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="warning-box"><h3>📚 Keep Learning!</h3><p>You scored {correct_count}/8 - Review the lesson and try again!</p></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Retake Quiz"):
                st.session_state.quiz_submitted = False
                st.session_state.quiz_answers = {}
                st.rerun()
        
        with col2:
            if st.button("🎯 New Topic"):
                st.session_state.current_lesson = None
                st.session_state.lesson_topic = ""
                st.session_state.quiz_questions = []
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.rerun()

def main():
    """Main application logic"""
    # Initialize database on first run
    init_database()
    
    if not st.session_state.logged_in:
        login_page()
    else:
        lesson_page()

if __name__ == "__main__":
    main()