import cv2
import numpy as np
import config
import os

# --- LOAD MODELS ---
# 1. Face Detector (Standard Haar Cascade)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# 2. Emotion Model (ONNX)
# We load the file directly. This never fails as long as the file exists.
model_filename = "emotion-ferplus-8.onnx"
model_path = os.path.join(os.path.dirname(__file__), model_filename)

# Check if file exists to prevent vague errors
if not os.path.exists(model_path):
    raise FileNotFoundError(f"❌ CRITICAL ERROR: missing {model_filename}. Please download it and place it in the services folder.")

# Load the network into OpenCV
emotion_net = cv2.dnn.readNetFromONNX(model_path)

# The FER+ model outputs these 8 specific emotions
EMOTIONS = ['Neutral', 'Happy', 'Surprise', 'Sad', 'Anger', 'Disgust', 'Fear', 'Contempt']

class VideoService:
    def __init__(self):
        self.video = cv2.VideoCapture(0)
        self.current_emotion = "Neutral"
        self.frame_count = 0
        print(">>> Video Service Initialized (ONNX Mode)")

    def get_frame(self, shared_state):
        success, image = self.video.read()
        if not success: return None

        # 1. Detect Faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        for (x, y, w, h) in faces:
            cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # 2. Emotion Analysis (Run every 5 frames)
            if self.frame_count % 5 == 0:
                try:
                    # ROI: Region of Interest (The Face)
                    face_roi = gray[y:y+h, x:x+w]
                    
                    # Preprocessing specific to FER+ Model:
                    # Resize to 64x64
                    face_roi = cv2.resize(face_roi, (64, 64))
                    
                    # Create Blob (Standardize image)
                    blob = cv2.dnn.blobFromImage(face_roi, 1.0, (64, 64), (0, 0, 0), swapRB=False, crop=False)
                    
                    # Forward Pass (Run the AI)
                    emotion_net.setInput(blob)
                    scores = emotion_net.forward()
                    
                    # Result is a list of scores, pick the highest one
                    scores = scores[0] 
                    softmax_scores = np.exp(scores) / np.sum(np.exp(scores)) # Convert to %
                    pred_index = np.argmax(softmax_scores)
                    
                    # Store result
                    self.current_emotion = EMOTIONS[pred_index]
                    
                    # Update Global State (Lowercase to match your logic.py)
                    shared_state["face_emotion"] = self.current_emotion.lower()
                    
                except Exception as e:
                    print(f"Emotion Error: {e}")

            # Draw Label
            cv2.putText(image, self.current_emotion, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36, 255, 12), 2)
        
        self.frame_count += 1
        
        # 3. Draw UI
        self.draw_ui(image, shared_state)
        
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()

    def draw_ui(self, image, state):
        h, w, _ = image.shape
        
        # Top Status Bar
        cv2.rectangle(image, (0, 0), (w, 40), (50, 50, 50), -1)
        status = state.get("system_status", "Init")
        col = (0, 255, 0) if "SPEAKING" in status else (0, 0, 255)
        cv2.putText(image, f"STATUS: {status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

        # Bottom Transcript Bar
        cv2.rectangle(image, (0, h-60), (w, h), (0, 0, 0), -1)
        transcript = state.get("transcript", "")
        cv2.putText(image, f"You: {transcript}", (10, h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Debug Overlay
        if config.DEBUG:
            cv2.putText(image, f"FACE: {state.get('face_emotion', '-')}", (w-200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 1)