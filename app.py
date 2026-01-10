from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import database  # Import our new DB manager

# Services
from services.audio_service import AudioService
from services.video_service import VideoService
from services.timeline_service import TimelineService
from services.llm_service import LLMService

app = Flask(__name__)
CORS(app)

# Initialize DB on start
database.init_db()

# Initialize Services
print("🚀 Booting up AI Services...")
audio_svc = AudioService()
video_svc = VideoService()
timeline_svc = TimelineService()
llm_svc = LLMService()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------
# 1. START INTERVIEW
# ---------------------------------------------------------
@app.route('/start_interview', methods=['POST'])
def start_interview():
    data = request.json
    name = data.get('name', 'Candidate')
    role = data.get('role', 'Junior Java Developer')

    # Create Session
    session_id = str(uuid.uuid4())[:8]  # Short ID
    database.create_session(session_id, name, role)

    # Hardcode Q1 to save time/cost
    first_question = f"Hello {name}. I see you are applying for the {role} position. Let's start. Please tell me about yourself and your background."

    return jsonify({
        "session_id": session_id,
        "question": first_question,
        "question_index": 1,
        "total_questions": 5
    })


# ---------------------------------------------------------
# 2. SUBMIT RESPONSE (THE CORE LOOP)
# ---------------------------------------------------------
@app.route('/submit_response', methods=['POST'])
def submit_response():
    # 1. Check Files
    if 'video' not in request.files:
        return jsonify({"error": "No video file"}), 400

    # 2. Extract Form Data
    session_id = request.form.get('session_id')
    current_q_index = int(request.form.get('question_index', 1))
    current_q_text = request.form.get('question_text')

    # 3. Save Video Temporarily
    video_file = request.files['video']
    video_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{current_q_index}.mp4")
    video_file.save(video_path)

    try:
        # --- A. RUN LABS (Parallel-ish) ---
        print(f"▶️ Processing Q{current_q_index} for Session {session_id}...")

        # 1. Video Analysis (Head Pose, Gaze, Emotion Log)
        video_data = video_svc.analyze(video_path)

        # 2. Audio Analysis (Transcribe + Pitch Log)
        audio_data = audio_svc.analyze(video_path)

        # 3. Timeline Fusion (The Magic)
        timeline = timeline_svc.fuse(audio_data, video_data)

        # Attach timeline to video_data so it gets saved to DB (for Showoff reports)
        video_data['summary']['timeline_snippet'] = timeline[:5]  # Save first 5 events for preview

        # --- B. GET HISTORY & CONTEXT ---
        session_info, _ = database.get_full_report_data(session_id)
        chat_history = database.get_chat_history(session_id)

        # --- C. GEMINI ANALYSIS ---
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

        # --- D. SAVE TO DB ---
        # We save the SUMMARY metrics to the DB, not the massive frame logs (too big)
        database.save_response(
            session_id=session_id,
            q_index=current_q_index,
            question=current_q_text,
            transcript=audio_data['transcript'],
            audio_metrics=audio_data['global_metrics'],
            video_metrics=video_data['summary'],  # Includes timeline snippet now
            ai_feedback=llm_result['feedback'],
            ai_score=llm_result['score']
        )

        # --- E. CLEANUP & NEXT STEP ---
        if os.path.exists(video_path):
            os.remove(video_path)  # Delete video to save space

        if current_q_index >= 5:
            return jsonify({
                "status": "completed",
                "message": "Interview Finished."
            })
        else:
            return jsonify({
                "status": "next_question",
                "next_question": llm_result['next_question'],
                "next_index": current_q_index + 1,
                "feedback_preview": llm_result['feedback']  # Optional: Show feedback in frontend
            })

    except Exception as e:
        print(f"🔥 Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# 3. GENERATE REPORT
# ---------------------------------------------------------
@app.route('/generate_report', methods=['GET'])
def generate_report():
    session_id = request.args.get('session_id')
    session_info, responses = database.get_full_report_data(session_id)
    return jsonify({
        "candidate": session_info['candidate_name'],
        "role": session_info['target_role'],
        "history": responses
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)