# Configuration Settings
DEBUG = True


# Audio Thresholds
RMS_THRESHOLD_LOW = 300
RMS_THRESHOLD_HIGH = 1500

# Question Bank
QUESTIONS = {
    "start": "Hello! I am your AI interviewer. Let's start. Tell me about yourself.",
    "technical_easy": [
        "What is the difference between a list and a tuple?",
        "Explain what a Variable is."
    ],
    "technical_hard": [
        "How does Python memory management work?",
        "Explain the concept of Decorators."
    ],
    "soft_skill": [
        "Describe a time you faced a challenge.",
        "How do you handle deadline pressure?"
    ],
    "comfort": [
        "It seems like you are a bit stressed. Take a deep breath. Let's talk about your favorite project.",
        "No worries. Let's switch gears. What do you enjoy most about coding?",
    ]
}