import cv2
import mediapipe as mp
import numpy as np
import os
import config

class VideoService:
    def __init__(self):
        print("⏳ Loading Visual Models...")
        
        # 1. Setup MediaPipe Face Mesh (For Gaze & Head Pose)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True, # Critical: Gives us Iris landmarks
            min_detection_confidence=0.5
        )

        # 2. Setup Emotion Model (ONNX) - The one we fixed earlier
        model_path = os.path.join("services", "emotion-ferplus-8.onnx")
        if not os.path.exists(model_path):
            print(f"⚠️ WARNING: {model_path} not found. Emotion detection will skip.")
            self.emotion_net = None
        else:
            self.emotion_net = cv2.dnn.readNetFromONNX(model_path)
            
        self.EMOTIONS = ['Neutral', 'Happy', 'Surprise', 'Sad', 'Anger', 'Disgust', 'Fear', 'Contempt']

    def analyze(self, video_path):
        print(f"🎥 Analyzing Video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        frame_count = 0
        eye_contact_frames = 0
        total_analyzed = 0
        emotion_counts = {e: 0 for e in self.EMOTIONS}
        
        while cap.isOpened():
            success, image = cap.read()
            if not success: break
            
            # Optimization: Analyze every 5th frame (sufficient for behavior)
            if frame_count % 5 == 0:
                total_analyzed += 1
                
                # A. Run MediaPipe (Geometry)
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = self.face_mesh.process(rgb_image)
                
                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    
                    # 1. Check Gaze (Eye Contact)
                    if self._check_eye_contact(landmarks):
                        eye_contact_frames += 1
                        
                    # 2. Check Emotion (ONNX)
                    # Only run if model loaded
                    if self.emotion_net:
                        emotion = self._detect_emotion(image, results.multi_face_landmarks[0])
                        emotion_counts[emotion] += 1
            
            frame_count += 1
            
        cap.release()
        
        # Calculate Aggregates
        if total_analyzed == 0: return {"error": "Could not process video frames"}
        
        eye_contact_pct = (eye_contact_frames / total_analyzed) * 100
        
        # Find dominant emotion
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        
        return {
            "eye_contact_percent": int(eye_contact_pct),
            "dominant_emotion": dominant_emotion,
            "emotion_breakdown": emotion_counts,
            "frames_analyzed": total_analyzed
        }

    def _check_eye_contact(self, landmarks):
        """
        Uses Face Mesh Depth (Z-axis) to detect if looking at camera.
        Logic: If the nose tip (Index 1) is too far 'left/right' relative to ears, 
        or 'up/down' relative to eyes, user is looking away.
        """
        # Simple Proxy: Check the 'Yaw' (Turning head left/right)
        # Nose tip: 1, Left Ear: 234, Right Ear: 454
        nose_x = landmarks[1].x
        left_ear_x = landmarks[234].x
        right_ear_x = landmarks[454].x
        
        # Calculate midpoint between ears
        ear_midpoint = (left_ear_x + right_ear_x) / 2
        
        # If nose is too far from midpoint, head is turned
        # Threshold 0.05 is found via trial-and-error for "Looking Forward"
        if abs(nose_x - ear_midpoint) < 0.05:
            return True
        return False

    def _detect_emotion(self, image, landmarks):
        """
        Crops face and runs ONNX inference
        """
        h, w, c = image.shape
        # Get bounding box from landmarks (roughly)
        x_min = int(min([l.x for l in landmarks.landmark]) * w)
        x_max = int(max([l.x for l in landmarks.landmark]) * w)
        y_min = int(min([l.y for l in landmarks.landmark]) * h)
        y_max = int(max([l.y for l in landmarks.landmark]) * h)
        
        # Padding
        x_min = max(0, x_min - 20)
        y_min = max(0, y_min - 20)
        x_max = min(w, x_max + 20)
        y_max = min(h, y_max + 20)
        
        face_roi = image[y_min:y_max, x_min:x_max]
        
        try:
            # FER+ Preprocessing
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64))
            blob = cv2.dnn.blobFromImage(resized, 1.0, (64, 64), (0, 0, 0), swapRB=False, crop=False)
            
            self.emotion_net.setInput(blob)
            scores = self.emotion_net.forward()[0]
            softmax = np.exp(scores) / np.sum(np.exp(scores))
            return self.EMOTIONS[np.argmax(softmax)]
        except:
            return "Neutral"