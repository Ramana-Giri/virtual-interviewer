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

    def analyze_response(self, transcript, audio_metrics, video_metrics, content_metrics, current_question):
        """
        Analyzes a SINGLE answer to generate immediate feedback and the NEXT question.
        """
        
        # We assume the role of a Senior Technical Recruiter
        prompt = f"""
        You are a Senior Technical Recruiter. Analyze this specific interview response.
        
        CONTEXT:
        - Question Asked: "{current_question}"
        - Candidate Answer: "{transcript}"
        
        LAB DATA (Scientific Measurements):
        - ACOUSTIC: {json.dumps(audio_metrics)} 
          (Note: Jitter > 1.0% = Nervousness; WPM > 170 = Rushing)
        - VISUAL: {json.dumps(video_metrics)} 
          (Note: Eye Contact < 60% = Low Confidence; Dominant Emotion = {video_metrics.get('dominant_emotion')})
        - CONTENT: {json.dumps(content_metrics)} 
          (Note: Relevance < 70 = Off-topic)

        TASK:
        Generate a JSON response with:
        1. "feedback": A 2-sentence critique of their performance (Mental State + Content).
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