import pyttsx3

class TTSService:
    def speak(self, text):
        try:
            # Re-initializing engine per call to avoid threading conflicts
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")