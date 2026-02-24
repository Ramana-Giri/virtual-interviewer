from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS
from functools import wraps
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

print("🚀 Booting PrepSpark AI Services…")
audio_svc = AudioService()
video_svc = VideoService()
timeline_svc = TimelineService()
llm_svc = LLMService()
tts_svc = TTSService()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Question type schedule — matches frontend Q_TYPES map
Q_TYPE_SCHEDULE = {
    1: 'intro',
    2: 'technical',
    3: 'technical',
    4: 'technical',
    5: 'behavioural'
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


def speak(text: str) -> str | None:
    try:
        audio_bytes = tts_svc.synthesize(text, voice="onyx")
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"⚠️ TTS failed (non-fatal): {e}")
    return None

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400
    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be 3–30 characters."}), 400
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "Username: letters, numbers, underscores only."}), 400
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, result = database.register_user(username, email, password, full_name)
    if not success:
        return jsonify({"error": result}), 409
    return jsonify({"message": "Account created! Please log in."}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('username_or_email', '').strip()
    password = data.get('password', '')
    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400
    success, result = database.login_user(identifier, password)
    if not success:
        return jsonify({"error": result}), 401
    return jsonify({
        "message": "Login successful.",
        "token": result["token"],
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
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
# START INTERVIEW
# ─────────────────────────────────────────────

@app.route('/start_interview', methods=['POST'])
@require_auth
def start_interview():
    data = request.get_json() or {}
    name = data.get('name', 'Candidate').strip() or 'Candidate'
    role = data.get('role', 'Software Developer').strip() or 'Software Developer'

    session_id = str(uuid.uuid4())[:8]
    database.create_session(session_id, name, role, user_id=request.user_id)

    first_question = (
        f"Hello {name}, welcome to your PrepSpark practice session for the {role} role. "
        f"Let's start with a simple one — please tell me about yourself and your background."
    )

    audio_b64 = speak(first_question)
    return jsonify({
        "session_id": session_id,
        "question": first_question,
        "question_index": 1,
        "question_type": "intro",
        "total_questions": 5,
        "audio_b64": audio_b64
    })


# ─────────────────────────────────────────────
# SUBMIT RESPONSE
# ─────────────────────────────────────────────

@app.route('/submit_response', methods=['POST'])
@require_auth
def submit_response():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided."}), 400

    session_id = request.form.get('session_id', '').strip()
    current_q_text = request.form.get('question_text', '').strip()
    current_q_type = request.form.get('question_type', 'technical').strip()

    try:
        current_q_index = int(request.form.get('question_index', 1))
    except ValueError:
        return jsonify({"error": "Invalid question_index."}), 400

    if not session_id or not current_q_text:
        return jsonify({"error": "session_id and question_text are required."}), 400

    session_info, _ = database.get_full_report_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403

    video_file = request.files['video']
    video_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{current_q_index}.webm")
    video_file.save(video_path)

    try:
        print(f"▶️  Processing Q{current_q_index} [{current_q_type}] for session {session_id}…")

        video_data = video_svc.analyze(video_path)
        audio_data = audio_svc.analyze(video_path)
        timeline = timeline_svc.fuse(audio_data, video_data)

        transcript = audio_data.get('transcript', '')
        global_metrics = audio_data.get('global_metrics', {
            'wpm': 0, 'avg_pitch_hz': 0, 'pitch_variance': 0,
            'jitter_percent': 0, 'duration_seconds': 0
        })
        video_summary = video_data.get('summary', {})
        video_summary['timeline_snippet'] = timeline[:5]

        chat_history = database.get_chat_history(session_id) if current_q_index > 1 else []

        # Determine what the next question type should be
        next_index = current_q_index + 1
        next_q_type = Q_TYPE_SCHEDULE.get(next_index, 'technical')

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
            current_q_index=current_q_index
        )

        ai_feedback = llm_result.get('feedback', 'No feedback generated.')
        ai_score = llm_result.get('score', 0)
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
        print(f"🔥 Processing Error: {e}")
        import traceback; traceback.print_exc()
        if os.path.exists(video_path):
            os.remove(video_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

    if current_q_index >= 5:
        # Trigger report generation and cache it now
        _generate_and_cache_report(session_id, session_info)
        return jsonify({
            "status": "completed",
            "message": "Session complete.",
            "transcript": transcript
        })
    else:
        audio_b64 = speak(next_question)
        return jsonify({
            "status": "next_question",
            "next_question": next_question,
            "next_index": next_index,
            "next_type": next_q_type,
            "feedback_preview": ai_feedback,
            "audio_b64": audio_b64,
            "transcript": transcript
        })


def _generate_and_cache_report(session_id: str, session_info: dict):
    """Generates the final Gemini report and saves it to DB immediately after Q5."""
    try:
        print(f"📄 Generating and caching report for session {session_id}…")
        _, responses = database.get_full_report_data(session_id)

        interview_log = []
        for r in responses:
            try:
                audio_m = json.loads(r.get("audio_metrics") or "{}")
            except Exception:
                audio_m = {}
            try:
                video_m = json.loads(r.get("video_metrics") or "{}")
            except Exception:
                video_m = {}

            interview_log.append({
                "question_index": r.get("question_index"),
                "question_type": r.get("question_type", "technical"),
                "question": r.get("question_text"),
                "transcript": r.get("transcript"),
                "ai_score": r.get("ai_score", 0),
                "ai_feedback": r.get("ai_feedback", ""),
                "audio_metrics": audio_m,
                "video_metrics": video_m,
            })

        detailed_report = llm_svc.generate_final_report(interview_log)

        # Build the full payload that the frontend expects
        full_payload = {
            "candidate": session_info['candidate_name'],
            "role": session_info['target_role'],
            "session_id": session_id,
            "start_time": session_info.get("start_time", ""),
            "responses": interview_log,
            "report": detailed_report
        }

        database.save_report(session_id, full_payload)
        print(f"✅ Report cached for session {session_id}")
    except Exception as e:
        print(f"⚠️  Report generation failed (non-fatal): {e}")
        import traceback; traceback.print_exc()


# ─────────────────────────────────────────────
# GENERATE REPORT (load from cache)
# ─────────────────────────────────────────────

@app.route('/generate_report', methods=['GET'])
@require_auth
def generate_report():
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_report_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if not responses:
        return jsonify({"error": "No responses found. Complete the session first."}), 400

    # ── Try cache first ──
    cached = database.get_cached_report(session_id)
    if cached:
        print(f"📋 Serving cached report for session {session_id}")
        return jsonify(cached)

    # ── Cache miss — generate now (fallback for older sessions) ──
    print(f"⚙️  No cached report found, generating now for session {session_id}…")
    interview_log = []
    for r in responses:
        try:
            audio_m = json.loads(r.get("audio_metrics") or "{}")
        except Exception:
            audio_m = {}
        try:
            video_m = json.loads(r.get("video_metrics") or "{}")
        except Exception:
            video_m = {}
        interview_log.append({
            "question_index": r.get("question_index"),
            "question_type": r.get("question_type", "technical"),
            "question": r.get("question_text"),
            "transcript": r.get("transcript"),
            "ai_score": r.get("ai_score", 0),
            "ai_feedback": r.get("ai_feedback", ""),
            "audio_metrics": audio_m,
            "video_metrics": video_m,
        })

    detailed_report = llm_svc.generate_final_report(interview_log)
    payload = {
        "candidate": session_info['candidate_name'],
        "role": session_info['target_role'],
        "session_id": session_id,
        "start_time": session_info.get("start_time", ""),
        "responses": interview_log,
        "report": detailed_report
    }
    database.save_report(session_id, payload)  # cache it for next time
    return jsonify(payload)


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