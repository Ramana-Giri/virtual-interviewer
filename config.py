# config.py
from dotenv import load_dotenv
import os

load_dotenv()
# --- API KEYS ---
# Replace with your actual key from Google AI Studio
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- THRESHOLDS (The Science Numbers) ---
# Acoustic
NERVOUS_WPM_THRESHOLD = 160      # > 160 WPM = Rushing/Anxious
MIN_WPM_THRESHOLD = 90
FREEZE_PAUSE_DURATION = 3.0      # > 3.0s silence = Cognitive Load/Freezing
Jitter_THRESHOLD = 0.05         # > 1.5% Jitter = Voice Tremors (Nervousness)

# Visual
MIN_EYE_CONTACT_PERCENT = 60     # < 60% = Low Confidence

# Content
MIN_RELEVANCE_SCORE = 70         # < 70% = Off-topic / Vague