from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from functools import wraps
import os
import uuid
import re
import database

# Services
from services.audio_service import AudioService
from services.video_service import VideoService
from services.timeline_service import TimelineService
from services.llm_service import LLMService
from services.tts_service import TTSService

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize DB on start
database.init_db()

# Initialize Services
print("🚀 Booting up AI Services...")
audio_svc = AudioService()
video_svc = VideoService()
timeline_svc = TimelineService()
llm_svc = LLMService()
tts_svc = TTSService()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────
# AUTH MIDDLEWARE
# ─────────────────────────────────────────────

def require_auth(f):
    """Decorator that protects routes — requires a valid Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        user_id = database.validate_token(token)
        if not user_id:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# 1. AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    # --- Input Validation ---
    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be between 3 and 30 characters."}), 400

    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "Username can only contain letters, numbers, and underscores."}), 400

    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, result = database.register_user(username, email, password, full_name)
    if not success:
        return jsonify({"error": result}), 409  # Conflict

    return jsonify({"message": "Account created successfully! Please log in."}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
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
    return jsonify({"message": "Logged out successfully."})


@app.route('/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Returns info about the currently logged-in user."""
    return jsonify({"user_id": request.user_id})


# ─────────────────────────────────────────────
# 2. TTS ROUTE
# ─────────────────────────────────────────────

@app.route('/tts/speak', methods=['POST'])
@require_auth
def text_to_speech():
    """
    Accepts JSON: { "text": "...", "voice": "alloy" }
    Streams back MP3 audio of the spoken question.
    """
    data = request.get_json()
    text = data.get('text', '').strip()
    voice = data.get('voice', 'alloy')  # Options: alloy, echo, fable, onyx, nova, shimmer

    if not text:
        return jsonify({"error": "No text provided."}), 400

    audio_bytes = tts_svc.synthesize(text, voice=voice)
    if audio_bytes is None:
        return jsonify({"error": "TTS synthesis failed."}), 500

    return Response(audio_bytes, mimetype="audio/mpeg")


# ─────────────────────────────────────────────
# 3. START INTERVIEW
# ─────────────────────────────────────────────

@app.route('/start_interview', methods=['POST'])
@require_auth
def start_interview():
    data = request.get_json()
    name = data.get('name', 'Candidate')
    role = data.get('role', 'Junior Java Developer')

    session_id = str(uuid.uuid4())[:8]
    database.create_session(session_id, name, role, user_id=data.get('user_id',1))

    first_question = (
        f"Hello {name}. I see you are applying for the {role} position. "
        f"Let's start. Please tell me about yourself and your background."
    )

    return jsonify({
        "session_id": session_id,
        "question": first_question,
        "question_index": 1,
        "total_questions": 5
    })


# ─────────────────────────────────────────────
# 4. SUBMIT RESPONSE (THE CORE LOOP)
# ─────────────────────────────────────────────

@app.route('/submit_response', methods=['POST'])
@require_auth
def submit_response():
    if 'video' not in request.files:
        return jsonify({"error": "No video file"}), 400

    session_id = request.form.get('session_id')
    current_q_index = int(request.form.get('question_index', 1))
    current_q_text = request.form.get('question_text')

    if not session_id or not current_q_text:
        return jsonify({"error": "session_id and question_text are required."}), 400

    # Validate that this session belongs to the logged-in user
    session_info, _ = database.get_full_report_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied to this session."}), 403

    video_file = request.files['video']
    video_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{current_q_index}.mp4")
    video_file.save(video_path)

    try:
        print(f"▶️ Processing Q{current_q_index} for Session {session_id}...")

        video_data = video_svc.analyze(video_path)
        audio_data = audio_svc.analyze(video_path)
        timeline = timeline_svc.fuse(audio_data, video_data)
        video_data['summary']['timeline_snippet'] = timeline[:5]

        chat_history = []
        if current_q_index != 1:
            chat_history = database.get_chat_history(session_id)

        print("🧠 Asking Gemini...")
        llm_result = llm_svc.analyze_response(
            transcript=audio_data['transcript'],
            timeline=timeline,
            audio_summary=audio_data['global_metrics'],
            video_summary=video_data['summary'],
            current_question=current_q_text,
            chat_history=chat_history,
            target_role=session_info['target_role']
        )

        database.save_response(
            session_id=session_id,
            q_index=current_q_index,
            question=current_q_text,
            transcript=audio_data['transcript'],
            audio_metrics=audio_data['global_metrics'],
            video_metrics=video_data['summary'],
            timeline=timeline,
            ai_feedback=llm_result['feedback'],
            ai_score=llm_result['score']
        )

        if os.path.exists(video_path):
            os.remove(video_path)

        if current_q_index >= 5:
            return jsonify({
                "status": "completed",
                "message": "Interview Finished."
            })
        else:
            next_question = llm_result['next_question']
            return jsonify({
                "status": "next_question",
                "next_question": next_question,
                "next_index": current_q_index + 1,
                "feedback_preview": llm_result['feedback']
            })

    except Exception as e:
        print(f"🔥 Error: {e}")
        import traceback
        traceback.print_exc()
        if os.path.exists(video_path):
            os.remove(video_path)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# 5. GENERATE REPORT
# ─────────────────────────────────────────────

@app.route('/generate_report', methods=['GET'])
@require_auth
def generate_report():
    session_id = request.args.get('session_id')
    session_info, responses = database.get_full_report_data(session_id)

    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({
        "candidate": session_info['candidate_name'],
        "role": session_info['target_role'],
        "history": responses
    })


# ─────────────────────────────────────────────
# 6. USER DASHBOARD
# ─────────────────────────────────────────────

@app.route('/my_interviews', methods=['GET'])
@require_auth
def my_interviews():
    """Returns all past interviews for the logged-in user."""
    interviews = database.get_user_interviews(request.user_id)
    return jsonify({"interviews": interviews})


if __name__ == '__main__':
    app.run(debug=True, port=5000)