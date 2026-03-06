from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import re
import base64
import json
import database

from services.audio_service import AudioService
from services.video_service import VideoService
from services.timeline_service import TimelineService
from services.llm_service import LLMService
from services.tts_service import TTSService

app = Flask(__name__)
CORS(app, supports_credentials=True)

database.init_db()

print("🚀 Booting PrepSpark…")
audio_svc = AudioService()
video_svc = VideoService()
timeline_svc = TimelineService()
llm_svc = LLMService()
tts_svc = TTSService()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Q-type schedule shared between frontend and backend
Q_TYPE_SCHEDULE = {
    1: 'intro',
    2: 'technical',
    3: 'technical',
    4: 'technical',
    5: 'behavioural'
}
TOTAL_QUESTIONS = 5

# Supported language codes — used for basic validation on incoming requests.
# Whisper Large v3 supports many more; this is just a safeguard against typos.
SUPPORTED_LANGUAGES = {
    'hi', 'ta', 'te', 'bn', 'kn', 'ml', 'mr', 'pa', 'gu', 'ur', 'or', 'as',  # Indian
    'en', 'es', 'fr', 'de', 'ar', 'ja', 'zh', 'ko', 'pt', 'ru', 'it', 'nl',  # Global
    'tr', 'vi', 'th', 'id', 'auto'                                              # Others + auto-detect
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        user_id = database.validate_token(token)
        if not user_id:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def speak(text: str, language: str = 'en') -> str | None:
    """TTS → base64 MP3. Returns None if unavailable."""
    try:
        audio_bytes = tts_svc.synthesize(text, voice="onyx", language=language)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"⚠️  TTS failed (non-fatal): {e}")
    return None


def _validate_language(lang_code: str) -> str:
    """
    Validates and normalises a language code from the request.
    Falls back to 'en' if the code is unrecognised.
    """
    code = (lang_code or 'en').strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        print(f"⚠️  Unknown language code '{code}', defaulting to 'en'.")
        return 'en'
    return code


def _build_interview_log(responses: list) -> list:
    """Normalises DB response rows into the format the LLM and frontend expect."""
    log = []
    for r in responses:
        try:
            audio_m = json.loads(r.get("audio_metrics") or "{}")
        except Exception:
            audio_m = {}
        try:
            video_m = json.loads(r.get("video_metrics") or "{}")
        except Exception:
            video_m = {}
        log.append({
            "question_index": r.get("question_index"),
            "question_type":  r.get("question_type", "technical"),
            "question":       r.get("question_text"),
            "transcript":     r.get("transcript"),
            "ai_score":       r.get("ai_score", 0),
            "ai_feedback":    r.get("ai_feedback", ""),
            "audio_metrics":  audio_m,
            "video_metrics":  video_m,
        })
    return log


def _complete_session(session_id: str, session_info: dict):
    """
    Called once after Q5 is saved.
    1. Generates the final AI report (in the session language).
    2. Stores it in the `reports` table.
    3. Marks the interview as COMPLETED.
    """
    try:
        print(f"📄 Generating report for session {session_id}…")
        _, responses = database.get_full_session_data(session_id)
        interview_log = _build_interview_log(responses)

        language = session_info.get('language', 'en')
        detailed_report = llm_svc.generate_final_report(interview_log, language=language)

        full_payload = {
            "candidate":  session_info["candidate_name"],
            "role":       session_info["target_role"],
            "session_id": session_id,
            "start_time": session_info.get("start_time", ""),
            "language":   language,
            "responses":  interview_log,
            "report":     detailed_report
        }

        database.save_report(session_id, full_payload)
        database.mark_session_completed(session_id)
        print(f"✅ Session {session_id} marked COMPLETED.")
    except Exception as e:
        print(f"⚠️  Report generation failed: {e}")
        import traceback; traceback.print_exc()


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username  = data.get('username', '').strip()
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400
    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be 3–30 characters."}), 400
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "Username: letters, numbers, underscores only."}), 400
    if not re.match(r'^[\w\.\-]+@[\w\.\-]+\.\w{2,}$', email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, result = database.register_user(username, email, password, full_name)
    if not success:
        return jsonify({"error": result}), 409
    return jsonify({"message": "Account created! Please log in."}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data       = request.get_json() or {}
    identifier = data.get('username_or_email', '').strip()
    password   = data.get('password', '')
    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400
    success, result = database.login_user(identifier, password)
    if not success:
        return jsonify({"error": result}), 401
    return jsonify({
        "message": "Login successful.",
        "token":   result["token"],
        "user": {
            "user_id":   result["user_id"],
            "username":  result["username"],
            "full_name": result["full_name"]
        }
    })


@app.route('/auth/logout', methods=['POST'])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    database.logout_user(token)
    return jsonify({"message": "Logged out."})


@app.route('/auth/me', methods=['GET'])
@require_auth
def get_me():
    return jsonify({"user_id": request.user_id})


# ─────────────────────────────────────────────
# START NEW INTERVIEW
# ─────────────────────────────────────────────

@app.route('/start_interview', methods=['POST'])
@require_auth
def start_interview():
    data     = request.get_json() or {}
    name     = data.get('name', 'Candidate').strip() or 'Candidate'
    role     = data.get('role', 'Software Developer').strip() or 'Software Developer'
    language = _validate_language(data.get('language', 'en'))

    session_id = str(uuid.uuid4())[:8]
    database.create_session(session_id, name, role,
                             user_id=request.user_id,
                             language=language)

    # Generate a localised opening greeting via LLM instead of a hardcoded English string.
    print(f"🌐 Starting interview | lang={language} | role={role}")
    first_question = llm_svc.generate_opening_question(name, role, language=language)

    audio_b64 = speak(first_question, language=language)

    return jsonify({
        "session_id":       session_id,
        "question":         first_question,
        "question_index":   1,
        "question_type":    "intro",
        "total_questions":  TOTAL_QUESTIONS,
        "language":         language,
        "audio_b64":        audio_b64
    })


# ─────────────────────────────────────────────
# RESUME INTERVIEW
# ─────────────────────────────────────────────

@app.route('/resume_interview', methods=['GET'])
@require_auth
def resume_interview():
    """
    Returns the state needed to resume an IN_PROGRESS interview.
    Figures out the next unanswered question from saved responses,
    asks the LLM to generate it (in the session language), and returns it with TTS audio.
    """
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if session_info.get('status') == 'COMPLETED':
        return jsonify({"error": "This session is already completed."}), 400

    language = session_info.get('language', 'en')

    answered_indices = {r['question_index'] for r in responses}
    next_index = 1
    for i in range(1, TOTAL_QUESTIONS + 1):
        if i not in answered_indices:
            next_index = i
            break

    if next_index > TOTAL_QUESTIONS:
        return jsonify({"error": "All questions answered. Generate the report."}), 400

    next_q_type  = Q_TYPE_SCHEDULE.get(next_index, 'technical')
    chat_history = database.get_chat_history(session_id)

    print(f"🔄 Resuming session {session_id} at Q{next_index} [{next_q_type}] | lang={language}…")
    try:
        llm_result = llm_svc.generate_resume_question(
            target_role=session_info['target_role'],
            q_index=next_index,
            q_type=next_q_type,
            chat_history=chat_history,
            language=language
        )
        next_question = llm_result.get(
            'question',
            f"Let's continue. Question {next_index}: can you tell me about your experience with {session_info['target_role']} projects?"
        )
    except Exception as e:
        print(f"⚠️  LLM resume question failed: {e}")
        next_question = f"Welcome back! Continuing from question {next_index}. Can you tell me about a challenging project you've worked on?"

    audio_b64 = speak(next_question, language=language)

    # Return already-answered responses so the frontend can populate the transcript
    completed = []
    for r in responses:
        completed.append({
            "question_index": r["question_index"],
            "question_text":  r["question_text"],
            "question_type":  r.get("question_type", "technical"),
            "transcript":     r.get("transcript", ""),
        })

    return jsonify({
        "session_id":          session_id,
        "candidate_name":      session_info["candidate_name"],
        "target_role":         session_info["target_role"],
        "language":            language,
        "next_question_index": next_index,
        "next_question":       next_question,
        "next_question_type":  next_q_type,
        "total_questions":     TOTAL_QUESTIONS,
        "completed_responses": completed,
        "audio_b64":           audio_b64
    })


# ─────────────────────────────────────────────
# SUBMIT RESPONSE
# ─────────────────────────────────────────────

@app.route('/submit_response', methods=['POST'])
@require_auth
def submit_response():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided."}), 400

    session_id     = request.form.get('session_id', '').strip()
    current_q_text = request.form.get('question_text', '').strip()
    current_q_type = request.form.get('question_type', 'technical').strip()

    try:
        current_q_index = int(request.form.get('question_index', 1))
    except ValueError:
        return jsonify({"error": "Invalid question_index."}), 400

    if not session_id or not current_q_text:
        return jsonify({"error": "session_id and question_text are required."}), 400

    session_info, _ = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if session_info.get('status') == 'COMPLETED':
        return jsonify({"error": "This session is already completed."}), 400

    language = session_info.get('language', 'en')

    video_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{current_q_index}.webm")
    request.files['video'].save(video_path)

    try:
        print(f"▶️  Processing Q{current_q_index} [{current_q_type}] — session {session_id} | lang={language}")

        # Run video and audio analysis in parallel to cut wall-clock time ~50%.
        # audio_svc.analyze now receives the language hint for Whisper.
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_video = pool.submit(video_svc.analyze, video_path)
            f_audio = pool.submit(audio_svc.analyze, video_path, language)
            video_data = f_video.result()
            audio_data = f_audio.result()
        timeline = timeline_svc.fuse(audio_data, video_data)

        transcript     = audio_data.get('transcript', '')
        global_metrics = audio_data.get('global_metrics', {
            'wpm': 0, 'avg_pitch_hz': 0, 'pitch_variance': 0,
            'jitter_percent': 0, 'duration_seconds': 0
        })
        video_summary = video_data.get('summary', {})
        video_summary['timeline_snippet'] = timeline[:5]

        chat_history = database.get_chat_history(session_id) if current_q_index > 1 else []
        next_index   = current_q_index + 1
        next_q_type  = Q_TYPE_SCHEDULE.get(next_index, 'technical')

        print("🧠 AI evaluation…")
        llm_result = llm_svc.analyze_response(
            transcript=transcript,
            timeline=timeline,
            audio_summary=global_metrics,
            video_summary=video_summary,
            current_question=current_q_text,
            current_q_type=current_q_type,
            next_q_type=next_q_type,
            chat_history=chat_history,
            target_role=session_info['target_role'],
            current_q_index=current_q_index,
            language=language
        )

        ai_feedback   = llm_result.get('feedback', 'No feedback generated.')
        ai_score      = llm_result.get('score', 0)
        next_question = llm_result.get('next_question', '')

        database.save_response(
            session_id=session_id,
            q_index=current_q_index,
            question=current_q_text,
            question_type=current_q_type,
            transcript=transcript,
            audio_metrics=global_metrics,
            video_metrics=video_summary,
            timeline=timeline,
            ai_feedback=ai_feedback,
            ai_score=ai_score
        )

    except Exception as e:
        print(f"🔥 Processing error: {e}")
        import traceback; traceback.print_exc()
        if os.path.exists(video_path):
            os.remove(video_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

    # ── Last question ──
    if current_q_index >= TOTAL_QUESTIONS:
        _complete_session(session_id, session_info)
        return jsonify({
            "status":     "completed",
            "message":    "Session complete.",
            "transcript": transcript
        })

    # ── More questions remaining ──
    audio_b64 = speak(next_question, language=language)
    return jsonify({
        "status":           "next_question",
        "next_question":    next_question,
        "next_index":       next_index,
        "next_type":        next_q_type,
        "feedback_preview": ai_feedback,
        "audio_b64":        audio_b64,
        "transcript":       transcript
    })


# ─────────────────────────────────────────────
# GET REPORT
# ─────────────────────────────────────────────

@app.route('/generate_report', methods=['GET'])
@require_auth
def get_report():
    """
    Returns the stored report for a COMPLETED session.
    Reports are generated exactly once (in _complete_session) and stored in the DB.
    This endpoint only reads; it never regenerates.
    """
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403

    if session_info.get('status') != 'COMPLETED':
        return jsonify({
            "error":  "This session is not yet complete. Finish all 5 questions first.",
            "status": session_info.get('status', 'IN_PROGRESS')
        }), 400

    report = database.get_stored_report(session_id)
    if not report:
        # Edge case: status=COMPLETED but report missing (e.g. server crashed mid-write).
        # Regenerate once and save it.
        print(f"⚠️  Report missing for completed session {session_id}. Regenerating…")
        language = session_info.get('language', 'en')
        interview_log   = _build_interview_log(responses)
        detailed_report = llm_svc.generate_final_report(interview_log, language=language)
        report = {
            "candidate":  session_info["candidate_name"],
            "role":       session_info["target_role"],
            "session_id": session_id,
            "start_time": session_info.get("start_time", ""),
            "language":   language,
            "responses":  interview_log,
            "report":     detailed_report
        }
        database.save_report(session_id, report)

    return jsonify(report)


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@app.route('/my_interviews', methods=['GET'])
@require_auth
def my_interviews():
    interviews = database.get_user_interviews(request.user_id)
    return jsonify({"interviews": interviews})


if __name__ == '__main__':
    app.run(debug=True, port=5000)