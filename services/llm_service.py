import google.generativeai as genai
import config
import json
import os

# Configure Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

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

        {history_text}
        
        CONTEXT:
        - Question Asked: "{current_question}"
        - Candidate Answer: "{transcript}"
        
        BEHAVIORAL TIMELINE (The "Game Tape"):
        {timeline_str}
        
        LAB DATA (Scientific Measurements):
        - ACOUSTIC: {json.dumps(audio_summary)} 
          (Note: Jitter > 1.0% = Nervousness; WPM > 170 = Rushing)
        - VISUAL: {json.dumps(video_summary)} 
          (Note: Eye Contact < 60% = Low Confidence; Dominant Emotion = {video_summary.get('dominant_emotion')})

        TASK:
        Generate a JSON response with:
        1. Analyze the candidate's performance (Mental State + Content).
        2. "next_question": A follow-up question. If they struggled, ask something easier. If they did well, dig deeper.
        3. "score": A score out of 10 for this specific answer.
        
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