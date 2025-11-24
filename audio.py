import speech_recognition as sr
from textblob import TextBlob
import time

def listen_and_analyze():
    # Initialize the recognizer
    recognizer = sr.Recognizer()

    # Use the default microphone
    with sr.Microphone() as source:
        print("\n🎧 Adjusting for ambient noise... (Please wait)")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🟢 LISTENING... (Speak a sentence)")

        try:
            # Listen for audio (times out after 5 seconds of silence)
            audio_data = recognizer.listen(source, timeout=5)
            print("⏳ Processing...")

            # 1. Speech to Text (STT)
            text = recognizer.recognize_google(audio_data)
            print(f"📝 You said: '{text}'")

            # 2. NLP Analysis (Sentiment)
            blob = TextBlob(text)
            sentiment_polarity = blob.sentiment.polarity
            # Polarity is between -1 (Negative) and +1 (Positive)

            if sentiment_polarity > 0.3:
                emotion = "Positive/Confident"
            elif sentiment_polarity < -0.3:
                emotion = "Negative/Stressed"
            else:
                emotion = "Neutral/Objective"

            print(f"🧠 NLP Analysis: {emotion} (Score: {sentiment_polarity:.2f})")
            return text, emotion

        except sr.WaitTimeoutError:
            print("❌ No speech detected.")
            return None, None
        except sr.UnknownValueError:
            print("❌ Could not understand audio.")
            return None, None
        except sr.RequestError:
            print("❌ Internet connection required for STT.")
            return None, None

if __name__ == "__main__":
    # Test loop
    while True:
        listen_and_analyze()
        if input("Press Enter to listen again (or 'q' to quit): ") == 'q':
            break