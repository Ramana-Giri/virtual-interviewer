# config.py
import os

# --- API KEYS ---
# Replace with your actual key from Google AI Studio
GEMINI_API_KEY = "AIzaSyCYRcKPYCRYS-YMnGu8aFcVmfDkaYGs2d4"

# --- THRESHOLDS (The Science Numbers) ---
# Acoustic
NERVOUS_WPM_THRESHOLD = 160      # > 160 WPM = Rushing/Anxious
FREEZE_PAUSE_DURATION = 3.0      # > 3.0s silence = Cognitive Load/Freezing
JITTER_THRESHOLD = 0.015         # > 1.5% Jitter = Voice Tremors (Nervousness)

# Visual
MIN_EYE_CONTACT_PERCENT = 60     # < 60% = Low Confidence

# Content
MIN_RELEVANCE_SCORE = 70         # < 70% = Off-topic / Vague