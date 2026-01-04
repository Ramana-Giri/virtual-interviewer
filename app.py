from flask import Flask, render_template, Response, jsonify
from services.video_service import VideoService
from core.logic import InterviewerBrain

app = Flask(__name__)

shared_state = {
    "face_emotion": "Neutral",
    "audio_emotion": "Waiting...",
    "transcript": "",
    "energy": "Medium",
    "system_status": "Initializing...",
    "interview_complete": False # Logic sets this to True when done
}

video_svc = VideoService()
brain = InterviewerBrain(shared_state)
brain.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

# NEW: API to check if interview is done
@app.route('/check_status')
def check_status():
    if shared_state["interview_complete"]:
        return jsonify({"status": "complete"})
    return jsonify({"status": "running"})

# NEW: The Report Page
@app.route('/report')
def report():
    # Pass the log data to the HTML
    return render_template('report.html', logs=brain.interview_log)

def gen():
    while True:
        frame = video_svc.get_frame(shared_state)
        if frame:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)