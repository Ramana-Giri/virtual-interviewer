import threading
import time
import config
from services.audio_service import AudioService
from services.tts_service import TTSService


class InterviewerBrain:
    def __init__(self, shared_state):
        self.audio_svc = AudioService()
        self.tts_svc = TTSService()
        self.state = shared_state  # Dictionary shared with Flask/Video
        self.running = True

    def start(self):
        # Run logic in a separate thread
        t = threading.Thread(target=self._game_loop)
        t.daemon = True
        t.start()

    def _game_loop(self):
        self.state["system_status"] = "🤖 SPEAKING..."
        self.tts_svc.speak(config.QUESTIONS["start"])

        while self.running:
            self.state["system_status"] = "🔴 LISTENING..."

            # 1. Listen
            data = self.audio_svc.listen_and_analyze()

            if data["status"] == "Success":
                self.state["system_status"] = "🟡 THINKING..."

                # Update Shared State for UI
                self.state["transcript"] = data["text"]
                self.state["audio_emotion"] = data["sentiment"]
                self.state["energy"] = data["energy"]

                # 2. Logic (Face + Audio)
                face_emo = self.state.get("face_emotion", "neutral")

                if face_emo in ['fear', 'sad'] or data["energy"] == "Low":
                    next_q = config.QUESTIONS["comfort"][0]
                elif face_emo == 'happy' and data["energy"] == "High":
                    next_q = config.QUESTIONS["technical_hard"][0]
                else:
                    next_q = config.QUESTIONS["technical_easy"][0]

                # 3. Respond
                self.state["system_status"] = "🤖 SPEAKING..."
                self.tts_svc.speak(next_q)
            else:
                pass  # Loop again if nothing heard