import threading
import time
import random # NEW: To pick random questions from a list
import config
from services.audio_service import AudioService
from services.tts_service import TTSService

class InterviewerBrain:
    def __init__(self, shared_state):
        self.audio_svc = AudioService()
        self.tts_svc = TTSService()
        self.state = shared_state
        self.running = True
        
        self.question_count = 0
        self.max_questions = 4
        
        # MEMORY: Keep track of asked questions to avoid repetition
        self.asked_questions = set() 
        self.interview_log = []

    def start(self):
        t = threading.Thread(target=self._game_loop)
        t.daemon = True
        t.start()

    def get_next_question(self, last_answer, face_emotion, energy):
        """
        The Smart Selector Logic
        """
        # 1. COMFORT CHECK: If user is very stressed, override everything
        if face_emotion in ['fear', 'sad'] or energy == "Low":
            candidates = config.TOPIC_QUESTIONS["comfort"]
            # Find one we haven't asked yet
            for q in candidates:
                if q not in self.asked_questions:
                    return q
        
        # 2. KEYWORD MATCHING: Scan answer for topics
        last_answer = last_answer.lower()
        potential_topics = []
        
        if "python" in last_answer: potential_topics += config.TOPIC_QUESTIONS["python"]
        if "java" in last_answer: potential_topics += config.TOPIC_QUESTIONS["java"]
        if "project" in last_answer or "built" in last_answer: potential_topics += config.TOPIC_QUESTIONS["project"]
        if "team" in last_answer or "group" in last_answer: potential_topics += config.TOPIC_QUESTIONS["team"]
        
        # 3. FILTERING: Remove already asked questions
        valid_candidates = [q for q in potential_topics if q not in self.asked_questions]
        
        # 4. SELECTION
        if valid_candidates:
            # We found a relevant follow-up!
            print(f">>> CONTEXT FOUND! Topics matched in: '{last_answer}'")
            return random.choice(valid_candidates)
        else:
            # No keyword matched? Fallback to General Questions
            print(">>> NO CONTEXT. Using Default.")
            defaults = config.TOPIC_QUESTIONS["default_hard"] if energy == "High" else config.TOPIC_QUESTIONS["default_easy"]
            remaining_defaults = [q for q in defaults if q not in self.asked_questions]
            
            if remaining_defaults:
                return random.choice(remaining_defaults)
            else:
                return "I have no further questions. Thank you."

    def _game_loop(self):
        # 1. Introduction
        self.update_ui("🤖 SPEAKING...", "Welcome.")
        self.safe_speak(config.START_QUESTION)
        self.asked_questions.add(config.START_QUESTION) # Mark as asked
        
        time.sleep(1)

        while self.running and self.question_count < self.max_questions:
            
            # --- LISTEN FIRST (To get the context for the NEXT question) ---
            # Wait for user to answer the PREVIOUS question
            answer_text = self.listen_retrying()
            
            if not answer_text:
                self.safe_speak("Let's move to the next topic.")
                answer_text = "" # Empty answer

            # --- DECIDE NEXT QUESTION BASED ON ANSWER ---
            # We use the answer we just heard to pick the next Q
            next_q = self.get_next_question(
                last_answer=answer_text,
                face_emotion=self.state.get("face_emotion", "neutral"),
                energy=self.state.get("energy", "Medium")
            )
            
            # Save to Memory so we don't repeat
            self.asked_questions.add(next_q)

            # --- ASK QUESTION ---
            self.question_count += 1
            self.update_ui("🤖 SPEAKING...", f"Q{self.question_count}: {next_q}")
            self.safe_speak(next_q)
            
        # Conclusion
        self.update_ui("🏁 FINISHED", "Generating Report...")
        self.safe_speak("Thank you. The interview is over.")
        self.state["interview_complete"] = True

    def listen_retrying(self):
        """
        Helper to listen with retry logic
        """
        attempts = 0
        while attempts < 2:
            self.update_ui("🔴 LISTENING...", "Waiting for answer...")
            data = self.audio_svc.listen_and_analyze()
            
            if data["status"] == "Success":
                self.update_ui("🟡 ANALYZING...", "Processing...")
                # Log it
                entry = {
                    "answer": data["text"],
                    "voice_emotion": data["sentiment"],
                    "face_emotion": self.state.get("face_emotion", "neutral")
                }
                self.interview_log.append(entry)
                
                # Update UI
                self.state["transcript"] = data["text"]
                self.state["audio_emotion"] = data["sentiment"]
                self.state["energy"] = data["energy"]
                return data["text"]
            else:
                attempts += 1
                self.update_ui("👂 LISTENING...", "I didn't catch that...")
        return None

    def update_ui(self, status, transcript):
        self.state["system_status"] = status
        self.state["transcript"] = transcript

    def safe_speak(self, text):
        self.state["system_status"] = "🤖 SPEAKING..."
        self.tts_svc.speak(text)
        self.state["system_status"] = "🔴 LISTENING..."