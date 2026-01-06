from flask import Flask, request, jsonify
from flask_cors import CORS
import os

# Import our 3 Labs + Brain
from services.audio_service import AudioService
from services.video_service import VideoService
from services.content_service import ContentService
from services.llm_service import LLMService

app = Flask(__name__)
CORS(app) # Allow frontend to talk to us later

# Initialize Services
audio_svc = AudioService()
video_svc = VideoService()
content_svc = ContentService()
llm_svc = LLMService()

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/analyze', methods=['POST'])
def analyze_video():
    """
    MVP Endpoint: Receives a video, runs full analysis, returns Micro-Feedback.
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video_file = request.files['video']
    
    # 1. Save Video Locally
    video_path = os.path.join(UPLOAD_FOLDER, video_file.filename)
    video_file.save(video_path)
    
    # Context (For MVP, we simulate these)
    current_question = request.form.get('question', "Tell me about yourself.")
    # In real app, we extract transcript from audio. 
    # For MVP speed, we can assume audio_svc handles transcription internally.
    
    try:
        # --- 🧪 PHASE 1: THE LABS ---
        print(f"▶️ Starting Analysis for {video_file.filename}...")
        
        # A. Audio Lab (Transcript + Acoustics)
        audio_data = audio_svc.analyze(video_path)
        if "error" in audio_data: return jsonify(audio_data), 500
        
        transcript = audio_data['transcript']
        
        # B. Video Lab (Visuals)
        video_data = video_svc.analyze(video_path)
        
        # C. Content Lab (Semantics)
        # We extract keywords from the Question to define 'Relevance'
        # Simple proxy: Use the words in the question as the topic
        keywords = current_question.lower().split()
        content_data = content_svc.analyze(transcript, keywords)
        
        # --- 🧠 PHASE 2: THE BRAIN ---
        print("🧠 Sending data to Gemini...")
        llm_result = llm_svc.analyze_response(
            transcript, 
            audio_data['metrics'], 
            video_data, 
            content_data, 
            current_question
        )
        
        # Combine everything into one debug response
        full_report = {
            "scientific_metrics": {
                "acoustic": audio_data['metrics'],
                "visual": video_data,
                "content": content_data
            },
            "ai_feedback": llm_result
        }
        
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
            
        return jsonify(full_report)

    except Exception as e:
        print(f"🔥 Critical Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run on port 5000
    app.run(debug=True, port=5000)