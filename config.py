# config.py

# --- AUDIO THRESHOLDS ---
DEBUG = True
RMS_THRESHOLD_LOW = 100 
RMS_THRESHOLD_HIGH = 800

# --- SMART QUESTION BANK ---
# Format: "Topic Keyword": ["Question 1", "Question 2"]
# We will search the User's Answer for these keywords.
TOPIC_QUESTIONS = {
    "python": [
        "You mentioned Python. Can you explain how memory management works in Python?",
        "What are Python Decorators and how have you used them?",
        "Difference between list and tuple?"
    ],
    "project": [
        "That sounds like a great project. What was the most difficult technical challenge you faced?",
        "How did you handle version control and collaboration in your project?"
    ],
    "team": [
        "Working in teams can be tough. How do you handle conflicts with teammates?",
        "Describe a time you had to lead a team initiative."
    ],
    "java": [
        "Since you know Java, explain the difference between JDK, JRE, and JVM.",
        "How does Garbage Collection work in Java?"
    ],
    "default_hard": [
        "Let's dive deeper. Explain the concept of REST APIs.",
        "How do you optimize a slow database query?"
    ],
    "default_easy": [
        "What is your favorite programming language and why?",
        "Explain the concept of OOPs."
    ],
    "comfort": [
        "You seem a bit stressed. Let's take a step back. What do you do for fun?",
        "No worries. Take your time. Tell me about your hobbies."
    ]
}

# The starting question
START_QUESTION = "Hello. I am your AI interviewer. Please introduce yourself and mention your technical skills."