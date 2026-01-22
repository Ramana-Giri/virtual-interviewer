import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class LLMService:
    def __init__(self):

        # 1.5 Flash is the best balance of Speed/Cost/Intelligence
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    def analyze_response(self, transcript, timeline, audio_summary, video_summary, current_question, chat_history, target_role):
        """
        Analyzes the answer AND generates the next question to save API calls.
        """

        history_text = ""
        if chat_history:
            history_text = "PREVIOUS CONVERSATION:\n"
            for item in chat_history:
                history_text += f"- Q: {item.get('q_text', '')}\n  A: {item.get('transcript', '')}\n"

        # 2. Format the Timeline for the Prompt
        # We convert the JSON list into a readable story for the LLM
        timeline_str = ""
        for event in timeline:
            t = event['timestamp']
            word = event.get('spoken', event.get('event', ''))
            beh = event.get('behavior', {})

            if event.get('event') == "LONG_PAUSE":
                timeline_str += f"[{t}] (SILENCE for {event.get('duration')}): Candidate was {beh}\n"
            else:
                # Normal speech event
                posture = beh.get('posture', 'Static')
                eye = beh.get('eye_contact', 'Screen')
                face = beh.get('expression', 'Neutral')
                timeline_str += f"[{t}] Spoke '{word}': Head={posture}, Eyes={eye}, Face={face}\n"

        prompt = f"""
        You are a Senior Technical Recruiter interviewing a candidate for a {target_role} role.
        CURRENT STATUS: Question {current_question} of 5.

        {history_text}
        
        PRIME DIRECTIVE (CRITICAL):
        1. **IGNORE IRRELEVANT BACKSTORY:** If the candidate talks about teaching, hobbies, or unrelated jobs, do NOT ask follow-up questions about them.
        2. **PIVOT TO THE ROLE:** Acknowledge their answer briefly, then immediately transition to a core competency required for a {target_role} (e.g., Databases, APIs, Algorithms, System Design).
        3. **CHECKLIST:** Ensure you have gathered evidence on the core skills for {target_role} by the end of Question 5.
        
        DECISION LOGIC FOR "next_question":
        - IF answer was IRRELEVANT: Pivot hard. (e.g., "That's interesting context. However, for this Java role, we need strong backend skills. Tell me about...")
        - IF answer was GOOD: Move to the next required skill in your checklist (e.g., "Great. Now let's talk about Cloud deployment.")
        - IF Question 5 of 5: This is the last question. Wrap up or ask one final "Hail Mary" technical check.
        
        CONTEXT:
        - Question Asked: "{current_question}"
        - Candidate Answer: "{transcript}"
        
        BEHAVIORAL TIMELINE:
        {timeline_str}
        
        LAB DATA (Scientific Measurements):
        - ACOUSTIC: {json.dumps(audio_summary)} 
          (Note: Jitter > 1.5% = Nervousness; WPM > 170 = Rushing)
        - VISUAL: {json.dumps(video_summary)} 
          (Note: Eye Contact < 60% = Low Confidence; Dominant Emotion = {video_summary.get('dominant_emotion')})

        TASK:
        Generate a JSON response with:
        - Analyze the candidate's performance (Mental State + Content).
        - Check if the answer is relevant to the question asked
        - Check if the candidate doesn't contradict with his previous answers.
        - "next_question": A follow-up question keeping in mind about you are at {current_question} question out of 5 questions to ask and you have to ask the question based on the candidates's answer as well as to check if the candidate posses all the skills and qualities for the role {target_role}
        - if {current_question} == 5, then you end the interview and give a final thank you for attending the interview in the place of next question.
        - "score": A score out of 10 for this specific answer.
        
        OUTPUT FORMAT: JSON Only.
        {{
            "feedback": "...",
            "next_question": "...",
            "score": 8
        }}
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Gemini Error: {e}")
            return {
                "feedback": "System error analyzing response.",
                "next_question": "Let's move on.",
                "score": 0
            }

    def generate_final_report(self, interview_log):
        """
        Generates the 'Executive Summary' after the interview is done.
        'interview_log' is a list of all Q&A data.
        """
        prompt = f"""
        Generate a Detailed Technical Performance Report for this candidate.
        
        INTERVIEW DATA:
        {json.dumps(interview_log)}
        
        REQUIREMENTS:
        1. Executive Summary: The "Vibe" vs. The "Value".
        2. Technical Depth: Analysis of keyword usage and concept clarity.
        3. Behavioral Signals: Analysis of Jitter, Pitch, and Eye Contact.
        4. Recommendation: Hire / No Hire / Training Needed.
        
        OUTPUT FORMAT: JSON.
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            return {"error": str(e)}


# ... (rest of your file)

if __name__ == "__main__":
    print("🧠 Initializing LLM Service Test...")

    # 1. Setup Mock Data (Simulating a "Game Tape")
    mock_transcript = "I built a task management app using Java Spring Boot. It was challenging because I had to learn Hibernate, but I eventually solved the database connection issues."

    mock_timeline = [
        {
            "timestamp": "0.0s - 3.5s",
            "spoken": "I built a task management app",
            "behavior": {"posture": "Nodding", "eye_contact": "Screen", "expression": "Happy"}
        },
        {
            "timestamp": "3.6s - 6.0s",
            "spoken": "It was challenging",
            "behavior": {"posture": "Static", "eye_contact": "Down", "expression": "Neutral"}
        },
        {
            "timestamp": "6.1s - 9.0s",
            "spoken": "solved the database connection",
            "behavior": {"posture": "Nodding", "eye_contact": "Screen", "expression": "Happy"}
        }
    ]

    mock_audio_stats = {"jitter_percent": 0.5, "wpm": 130}
    mock_video_stats = {"gaze_screen_pct": 85, "expressiveness": 50, "dominant_emotion": "Happy"}

    # 2. Run the Service
    try:
        service = LLMService()

        print("\n--- 🧪 Sending Prompt to Gemini... ---")
        result = service.analyze_response(
            transcript=mock_transcript,
            timeline=mock_timeline,
            audio_summary=mock_audio_stats,
            video_summary=mock_video_stats,
            current_question="Tell me about a project you are proud of.",
            chat_history=[],
            target_role="Junior Java Developer"
        )

        print("\n✅ GEMINI RESPONSE:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("Check your GEMINI_API_KEY in .env file!")