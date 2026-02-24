import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class LLMService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    def analyze_response(self, transcript, timeline, audio_summary, video_summary,
                         current_question, current_q_type, next_q_type,
                         chat_history, target_role, current_q_index):
        """
        Evaluates the candidate's answer and generates the next question.
        Question flow: Q1=intro, Q2-4=technical, Q5=behavioural.
        """

        history_text = ""
        if chat_history:
            history_text = "PREVIOUS CONVERSATION:\n"
            for item in chat_history:
                history_text += f"- Q: {item.get('q_text', '')}\n  A: {item.get('transcript', '')}\n"

        timeline_str = ""
        for event in timeline:
            t = event['timestamp']
            if event.get('event') == "LONG_PAUSE":
                timeline_str += f"[{t}] SILENCE ({event.get('duration')}): {event.get('behavior', '')}\n"
            else:
                beh = event.get('behavior', {})
                timeline_str += (
                    f"[{t}] '{event.get('spoken', '')}': "
                    f"Head={beh.get('posture','Static')}, "
                    f"Eyes={beh.get('eye_contact','Screen')}, "
                    f"Face={beh.get('expression','Neutral')}\n"
                )

        # ── Next question type instructions ──
        next_q_instructions = {
            'intro': "Ask a natural self-introduction question.",
            'technical': (
                f"Ask a TECHNICAL question relevant to a {target_role}. "
                f"Focus on core skills: data structures, algorithms, frameworks, system design, "
                f"databases, or role-specific tools. Make it concrete and progressively deeper "
                f"than previous questions. Do NOT ask about the candidate's personal life or hobbies."
            ),
            'behavioural': (
                f"This is the FINAL question (Q5). Ask ONE behavioural/situational question using "
                f"the STAR format (Situation, Task, Action, Result). Examples: "
                f"'Tell me about a time you handled a difficult deadline', "
                f"'Describe a situation where you disagreed with a teammate — how did you resolve it?', "
                f"'Give an example of a project you are proud of and your specific contribution.' "
                f"Then end with a warm closing like: 'That concludes our session. Thank you for practising with PrepSpark!'"
            )
        }.get(next_q_type, "Ask a relevant follow-up technical question.")

        is_last_question = current_q_index >= 5

        prompt = f"""
You are an AI interview coach at PrepSpark, a candidate practice platform (NOT a real hiring system).
You are helping a candidate practice for a {target_role} role.

CURRENT: Question {current_q_index} of 5 (type: {current_q_type}).
{"THIS IS THE LAST QUESTION — wrap up after evaluating." if is_last_question else f"NEXT question will be type: {next_q_type}."}

{history_text}

QUESTION ASKED: "{current_question}"
CANDIDATE ANSWER: "{transcript}"

BEHAVIOURAL TIMELINE:
{timeline_str if timeline_str else "(No timeline data available)"}

ACOUSTIC DATA: {json.dumps(audio_summary)}
  (Jitter > 1.5% = voice tremor/nervousness; WPM > 170 = rushing)
VISUAL DATA: {json.dumps(video_summary)}
  (Eye contact < 60% = low confidence; Dominant emotion = {video_summary.get('dominant_emotion', 'Neutral')})

EVALUATION RULES:
1. Score the answer honestly on technical accuracy, depth, and communication.
2. Check if the answer is relevant to the question asked.
3. Note any contradictions with previous answers.
4. Be constructive — this is a practice platform, so frame feedback as coaching tips.

NEXT QUESTION RULES:
{"- Do NOT generate a next question. Instead write a brief, warm closing message." if is_last_question else f"- {next_q_instructions}"}
- Keep questions concise (1-2 sentences max).
- Do NOT reveal scoring or say 'great answer' — stay neutral and professional.

Respond ONLY with valid JSON:
{{
  "feedback": "Detailed coaching feedback on this specific answer (2-4 sentences). Mention what was good and what to improve.",
  "next_question": "{'Thank you for completing this practice session with PrepSpark. Review your report for detailed feedback and tips to improve!' if is_last_question else 'Your next question here'}",
  "score": 7
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ AI Error: {e}")
            return {
                "feedback": "Could not analyse this response due to a system error.",
                "next_question": "Let's continue. Can you tell me about your experience with databases?",
                "score": 0
            }

    def generate_resume_question(self, target_role: str, q_index: int, q_type: str, chat_history: list) -> dict:
        """
        Generates the next question when a candidate resumes an interrupted session.
        Uses the prior conversation history so the question flows naturally.
        """
        history_text = ""
        if chat_history:
            history_text = "PREVIOUS Q&A:\n"
            for item in chat_history:
                history_text += f"- Q: {item.get('q_text', '')}\n  A: {item.get('transcript', '')[:200]}…\n"

        type_instructions = {
            'intro': "Ask a warm welcome-back introduction or background question.",
            'technical': f"Ask a specific technical question for a {target_role} role. Focus on skills, tools, algorithms, or system design. Be concrete.",
            'behavioural': "Ask a STAR-format behavioural question (Situation, Task, Action, Result). E.g. 'Tell me about a time you handled a tough deadline.'"
        }.get(q_type, "Ask a relevant technical question.")

        prompt = f"""
You are an AI interview coach at PrepSpark. A candidate is resuming their practice session for a {target_role} role at question {q_index} of 5.

{history_text}

Generate question {q_index} of 5 (type: {q_type}).
{type_instructions}

Rules:
- Keep it to 1-2 sentences.
- Make it naturally flow from previous answers if there are any.
- Do NOT greet or say 'welcome back' — the UI handles that.

Respond ONLY with JSON:
{{"question": "Your question here"}}
"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Resume question generation failed: {e}")
            return {"question": f"Question {q_index}: Can you describe a challenging problem you solved in a past project?"}

    def generate_final_report(self, interview_log):
        """
        Generates the executive performance report.
        Returns structured JSON that the report page renders.
        """
        prompt = f"""
You are an expert interview coach at PrepSpark, a candidate interview practice platform.
Generate a detailed, encouraging but honest performance report for this practice session.

INTERVIEW DATA:
{json.dumps(interview_log, indent=2)}

The interview had 5 questions: 1 introduction, 3 technical, 1 behavioural.

Generate a JSON report with EXACTLY these keys:
{{
  "executive_summary": "2-3 sentences summarising overall performance, strengths, and key areas to work on. Write in plain English — no jargon, no bullet points here.",
  "recommendation": "One of: 'Interview-Ready', 'Getting There — Keep Practising', 'More Practice Recommended'",
  "technical_depth": "Analysis of how well the candidate answered technical questions. What concepts did they demonstrate? What was missing?",
  "communication_style": "Analysis of how clearly and confidently the candidate communicated. Reference voice metrics (WPM, jitter) if available.",
  "behavioural_signals": "Analysis of body language, eye contact, and emotional expression patterns observed across the session.",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "areas_for_improvement": ["area 1", "area 2", "area 3"],
  "coaching_tips": "3-4 specific, actionable tips to help the candidate improve before their real interview."
}}

IMPORTANT:
- All string values must be plain readable prose or arrays of short strings — NO nested objects inside string fields.
- The "strengths" and "areas_for_improvement" fields must be JSON arrays of plain strings.
- Be honest but encouraging — this is practice, not a real rejection.
- Do not include any text outside the JSON object.
"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Report generation error: {e}")
            return {"error": str(e), "executive_summary": "Report generation encountered an error."}