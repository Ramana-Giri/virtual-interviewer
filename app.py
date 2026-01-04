from flask import Flask, render_template, Response
from services.video_service import VideoService
from core.logic import InterviewerBrain

app = Flask(__name__)

# Shared "Memory" for the whole app
shared_state = {
    "face_emotion": "Neutral",
    "audio_emotion": "Waiting...",
    "transcript": "",
    "energy": "Medium",
    "system_status": "Initializing..."
}

# Initialize Services
video_svc = VideoService()
brain = InterviewerBrain(shared_state)

# Start the Brain
brain.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen():
    while True:
        # Pass shared state so video can draw the UI text
        frame = video_svc.get_frame(shared_state)
        if frame:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)