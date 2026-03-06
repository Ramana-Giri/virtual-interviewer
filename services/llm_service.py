import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class LLMService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    # ─────────────────────────────────────────────
    # LANGUAGE SUPPORT
    # ─────────────────────────────────────────────

    # Maps ISO 639-1 codes to full language names used in prompts.
    # Gemini understands full names much more reliably than codes alone.
    LANGUAGE_NAMES = {
        # Indian languages
        'hi': 'Hindi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'bn': 'Bengali',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'mr': 'Marathi',
        'pa': 'Punjabi',
        'gu': 'Gujarati',
        'ur': 'Urdu',
        'or': 'Odia',
        'as': 'Assamese',
        # Global languages
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ar': 'Arabic',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'ko': 'Korean',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'it': 'Italian',
        'nl': 'Dutch',
        'tr': 'Turkish',
        'vi': 'Vietnamese',
        'th': 'Thai',
        'id': 'Indonesian',
    }

    def _lang_name(self, code: str) -> str:
        """Returns the full language name for a given ISO 639-1 code."""
        return self.LANGUAGE_NAMES.get(code.lower(), 'English')

    def _lang_instruction(self, language: str) -> str:
        """
        Returns the standard language instruction block prepended to every prompt.
        Instructs Gemini to write all content in the target language while keeping
        JSON keys in English so the frontend parser never breaks.
        """
        lang_name = self._lang_name(language)
        if language.lower() == 'en':
            return ""  # No instruction needed for English — it's the default
        return (
            f"LANGUAGE INSTRUCTION: You MUST write all response text in {lang_name}.\n"
            f"This includes feedback, questions, summaries, and any prose fields.\n"
            f"JSON keys must remain in English exactly as specified.\n"
            f"Only the VALUES of string fields should be in {lang_name}.\n"
            f"Do NOT mix languages. Do NOT fall back to English.\n\n"
        )

    # ─────────────────────────────────────────────
    # OPENING QUESTION (replaces hardcoded greeting in app.py)
    # ─────────────────────────────────────────────

    def generate_opening_question(self, candidate_name: str,
                                   target_role: str,
                                   language: str = 'en') -> str:
        """
        Generates a warm, localised opening greeting for the interview.
        Called from app.py start_interview() instead of a hardcoded English string.
        """
        lang_name = self._lang_name(language)
        lang_instruction = self._lang_instruction(language)

        prompt = f"""{lang_instruction}You are an AI interviewer for PrepSpark. Generate a warm, professional opening greeting for a mock interview.

Candidate name: {candidate_name}
Target role: {target_role}

The greeting should:
- Welcome the candidate by their first name
- Mention the role they are practising for
- Ask them to introduce themselves and their background
- Be 2-3 sentences, natural and friendly
- Be written entirely in {lang_name}

Respond with ONLY the greeting text. No JSON, no labels, no extra commentary."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"❌ Opening question error: {e}")
            # Safe English fallback
            return (
                f"Hello {candidate_name}, welcome to your PrepSpark practice session "
                f"for the {target_role} role. "
                f"Let's start — please tell me about yourself and your background."
            )

    # ─────────────────────────────────────────────
    # ANALYSE RESPONSE + GENERATE NEXT QUESTION
    # ─────────────────────────────────────────────

    def analyze_response(self, transcript, timeline, audio_summary, video_summary,
                         current_question, current_q_type, next_q_type,
                         chat_history, target_role, current_q_index,
                         language: str = 'en'):
        """
        Evaluates the candidate's answer.
        If current_q_index < 5: also generates the next question.
        If current_q_index == 5: this IS Q5 (behavioural) — no next question needed.

        Args:
            language: ISO 639-1 code. All feedback and next_question will be in this language.
        """
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)

        # ── Build history string ──
        history_text = ""
        if chat_history:
            history_text = "PREVIOUS CONVERSATION:\n"
            for item in chat_history:
                q = item.get('q_text', '')
                a = (item.get('transcript', '') or '')[:300]
                history_text += f"- Q: {q}\n  A: {a}\n"

        # ── Build timeline string ──
        timeline_str = ""
        for event in timeline[:20]:   # cap at 20 events
            t = event.get('timestamp', '')
            if event.get('event') == "LONG_PAUSE":
                timeline_str += f"[{t}] SILENCE ({event.get('duration', '')}s)\n"
            else:
                beh = event.get('behavior', {})
                timeline_str += (
                    f"[{t}] Eyes={beh.get('eye_contact', 'Screen')}, "
                    f"Face={beh.get('expression', 'Neutral')}\n"
                )

        is_last = (current_q_index >= 5)

        # ── Build next-question instruction (only used when NOT last) ──
        if not is_last:
            next_q_instructions = {
                'intro': "Ask a natural self-introduction or background question.",
                'technical': (
                    f"Ask ONE specific technical question for a {target_role} role. "
                    f"Focus on algorithms, system design, frameworks, or role-specific tools. "
                    f"Make it progressively harder than previous questions. "
                    f"Do NOT ask about personal life, hobbies, or team dynamics."
                ),
                'behavioural': (
                    f"Ask ONE behavioural question using STAR format. "
                    f"Choose from: 'Tell me about a time you handled a difficult deadline', "
                    f"'Describe a situation where you disagreed with a teammate and how you resolved it', "
                    f"'Give an example of a project you are proud of and your specific contribution', "
                    f"'Walk me through a time you had to learn something completely new under pressure'. "
                    f"Pick whichever fits best given the conversation so far."
                )
            }.get(next_q_type, "Ask a relevant follow-up technical question.")

            next_q_section = f"""
NEXT QUESTION (type: {next_q_type}):
{next_q_instructions}
Keep it to 1-2 sentences. Do not say "great answer" or reveal the score.
The next_question field MUST be written in {lang_name}.
"""
            next_q_json_field = '"next_question": "Your question for the candidate here (in {lang_name})"'.format(lang_name=lang_name)
        else:
            next_q_section = "This is the FINAL question. Do NOT generate another question."
            next_q_json_field = '"next_question": "A short closing message thanking the candidate and telling them their report is ready (written in {lang_name})"'.format(lang_name=lang_name)

        prompt = f"""{lang_instruction}You are an AI interview coach at PrepSpark helping a candidate practise for a {target_role} role.

CURRENT: Question {current_q_index} of 5 (type: {current_q_type})
{history_text}

QUESTION ASKED: "{current_question}"
CANDIDATE ANSWER: "{transcript}"

BEHAVIOURAL DATA (summarised):
{timeline_str if timeline_str else "(No timeline data)"}
Acoustics: WPM={audio_summary.get('wpm', 'N/A')}, Jitter={audio_summary.get('jitter_percent', 'N/A')}%
Eye contact: {video_summary.get('eye_contact_percent', 'N/A')}%, Emotion: {video_summary.get('dominant_emotion', 'Neutral')}

EVALUATION RULES:
1. Score 1-10 on technical accuracy, depth, clarity, and relevance.
2. If the answer is off-topic, note it specifically.
3. Feedback must be coaching-style (constructive, 2-3 sentences) written in {lang_name}.
4. Do NOT say "great answer", "well done", or reveal the numeric score in feedback.

{next_q_section}

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "feedback": "2-3 sentences of honest coaching feedback in {lang_name}",
  {next_q_json_field},
  "score": 7
}}"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)

            # Safety net: if it's the last question and next_question is still a
            # technical-sounding question, override it with a closing message.
            if is_last:
                nq = result.get('next_question', '')
                suspicious_starts = ('tell me', 'can you', 'describe', 'explain',
                                     'what is', 'what are', 'how would', 'walk me')
                if any(nq.lower().startswith(s) for s in suspicious_starts):
                    # Generate a proper closing in the right language
                    result['next_question'] = self._generate_closing_message(language)
            return result

        except Exception as e:
            print(f"❌ AI analyze_response error: {e}")
            fallback_next = (
                self._generate_closing_message(language)
                if is_last else
                f"Let's move on. For a {target_role} role, can you explain how you would approach "
                f"designing a scalable system for handling high traffic?"
            )
            return {
                "feedback": "Could not analyse this response due to a system error.",
                "next_question": fallback_next,
                "score": 0
            }

    def _generate_closing_message(self, language: str) -> str:
        """Generates a localised closing message when the interview ends."""
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)
        prompt = (
            f"{lang_instruction}Write a short 1-2 sentence closing message for a mock interview app "
            f"telling the candidate their practice session is complete and their detailed report is ready to view. "
            f"Be warm and encouraging. Write only in {lang_name}. No JSON, no labels."
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return (
                "That wraps up our practice session! Your report is ready — "
                "head over to review your scores and personalised coaching tips."
            )

    # ─────────────────────────────────────────────
    # RESUME QUESTION
    # ─────────────────────────────────────────────

    def generate_resume_question(self, target_role: str, q_index: int,
                                  q_type: str, chat_history: list,
                                  language: str = 'en') -> dict:
        """Generates the next question when a candidate resumes an interrupted session."""
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)

        history_text = ""
        if chat_history:
            history_text = "PREVIOUS Q&A:\n"
            for item in chat_history:
                history_text += f"- Q: {item.get('q_text', '')}\n  A: {(item.get('transcript', '') or '')[:200]}\n"

        type_instructions = {
            'intro':       "Ask a natural self-introduction or background question.",
            'technical':   f"Ask ONE concrete technical question for a {target_role} role (algorithms, system design, tools).",
            'behavioural': "Ask ONE STAR-format behavioural question (e.g. 'Tell me about a time you handled a tough deadline under pressure.')."
        }.get(q_type, "Ask a relevant technical question.")

        prompt = f"""{lang_instruction}You are an AI interview coach at PrepSpark. A candidate is resuming practice for a {target_role} role at question {q_index} of 5.

{history_text}
Generate question {q_index} of 5 (type: {q_type}).
{type_instructions}
Rules: 1-2 sentences, flows naturally from prior answers, no greeting or 'welcome back'.
The question MUST be written in {lang_name}.

Respond ONLY with JSON: {{"question": "Your question here in {lang_name}"}}"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Resume question error: {e}")
            return {"question": "Can you describe a challenging technical problem you solved recently and walk me through your approach?"}

    # ─────────────────────────────────────────────
    # FINAL REPORT
    # ─────────────────────────────────────────────

    def generate_final_report(self, interview_log: list,
                               language: str = 'en') -> dict:
        """
        Generates the executive performance report once, after Q5.
        All prose values in the report are written in the specified language.
        JSON keys always stay in English so the frontend never breaks.
        """
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)

        # Trim transcripts to keep prompt lean
        lean_log = []
        for r in interview_log:
            lean_log.append({
                "question_index": r.get("question_index"),
                "question_type":  r.get("question_type"),
                "question":       r.get("question"),
                "transcript":     (r.get("transcript") or "")[:400],
                "ai_score":       r.get("ai_score", 0),
                "ai_feedback":    r.get("ai_feedback", ""),
                "audio_metrics":  {
                    "wpm":            r.get("audio_metrics", {}).get("wpm"),
                    "jitter_percent": r.get("audio_metrics", {}).get("jitter_percent"),
                },
                "video_metrics": {
                    "eye_contact_percent": r.get("video_metrics", {}).get("eye_contact_percent"),
                    "dominant_emotion":    r.get("video_metrics", {}).get("dominant_emotion"),
                }
            })

        prompt = f"""{lang_instruction}You are an expert interview coach at PrepSpark generating a post-session performance report.

INTERVIEW DATA:
{json.dumps(lean_log, indent=2)}

The session had 5 questions: Q1=intro, Q2-Q4=technical, Q5=behavioural.

IMPORTANT: JSON keys must stay in English exactly as shown below.
Only the VALUES (the text content) must be written in {lang_name}.

Generate a JSON report with EXACTLY these keys:
{{
  "executive_summary": "2-3 plain sentences on overall performance, key strength, and the single most important thing to improve. Write in {lang_name}.",
  "recommendation": "One of exactly: 'Interview-Ready' | 'Getting There — Keep Practising' | 'More Practice Recommended'",
  "technical_depth": "Prose analysis of technical answers — what concepts were demonstrated, what was missing. Write in {lang_name}.",
  "communication_style": "Prose analysis of clarity, confidence, WPM, and jitter if data available. Write in {lang_name}.",
  "behavioural_signals": "Prose analysis of eye contact, emotion patterns, and composure observed. Write in {lang_name}.",
  "strengths": ["plain string in {lang_name}", "plain string in {lang_name}", "plain string in {lang_name}"],
  "areas_for_improvement": ["plain string in {lang_name}", "plain string in {lang_name}", "plain string in {lang_name}"],
  "coaching_tips": "3-4 specific, actionable tips to improve before a real interview. Write in {lang_name}."
}}

Rules:
- All string values = plain prose in {lang_name}. No nested objects inside strings.
- strengths and areas_for_improvement = JSON arrays of plain strings only.
- Be honest and encouraging — this is practice, not rejection.
- Output ONLY the JSON object, no markdown fences."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Report generation error: {e}")
            return {
                "error": str(e),
                "executive_summary": "Report generation encountered an error. Please try again.",
                "recommendation": "More Practice Recommended"
            }