import cv2
import mediapipe as mp
import numpy as np
import math
import os


class VideoService:
    def __init__(self):
        print("⏳ Loading Visual Models...")

        # 1. Configuration (Calibrated from your tests)
        self.SMOOTHING = 0.15
        self.H_MIN, self.H_MAX = 0.42, 0.58
        self.V_MIN, self.V_MAX = 0.35, 0.65
        self.BLINK_THRESH = 0.23

        # 2. Setup MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # Critical for Iris
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 3. Setup Emotion Model (Legacy - Keeping it for now)
        model_path = os.path.join("services", "emotion-ferplus-8.onnx")
        if os.path.exists(model_path):
            self.emotion_net = cv2.dnn.readNetFromONNX(model_path)
            self.has_emotion_net = True
        else:
            print("⚠️ Emotion Model not found. Skipping ONNX emotion detection.")
            self.has_emotion_net = False

        self.EMOTIONS = ['Neutral', 'Happy', 'Surprise', 'Sad', 'Anger', 'Disgust', 'Fear', 'Contempt']

    def analyze(self, video_path):
        print(f"🎥 Analyzing Video: {video_path}")
        cap = cv2.VideoCapture(video_path)

        # --- Metrics State ---
        stats = {
            "frames_total": 0,
            "frames_analyzed": 0,
            "blinks": 0,
            "gaze": {"Screen": 0, "Up": 0, "Down": 0, "Left": 0, "Right": 0},
            "emotion_counts": {e: 0 for e in self.EMOTIONS}
        }

        # Analysis Variables
        blink_active = False
        smoothed_h, smoothed_v = 0.5, 0.5
        raise_values, frown_values = [], []  # For Expressiveness

        while cap.isOpened():
            success, image = cap.read()
            if not success: break

            stats["frames_total"] += 1

            # Optimization: Analyze every 2nd frame to speed up processing
            if stats["frames_total"] % 2 != 0: continue

            stats["frames_analyzed"] += 1
            img_h, img_w = image.shape[:2]
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_image)

            if results.multi_face_landmarks:
                landmarks_mp = results.multi_face_landmarks[0].landmark
                mesh_points = np.array([np.multiply([p.x, p.y], [img_w, img_h]).astype(int)
                                        for p in landmarks_mp])

                # --- 1. GAZE TRACKING (Your Logic) ---
                smoothed_h, smoothed_v, direction = self._get_gaze_direction(
                    mesh_points, smoothed_h, smoothed_v
                )
                stats["gaze"][direction] += 1

                # --- 2. BLINK DETECTION ---
                ear = self._get_ear(landmarks_mp, [33, 160, 158, 133, 153, 144])
                if ear < self.BLINK_THRESH:
                    if not blink_active:
                        stats["blinks"] += 1
                        blink_active = True
                else:
                    blink_active = False

                # --- 3. EXPRESSIVENESS (Brows) ---
                r_val, f_val = self._get_brow_metrics(landmarks_mp)
                raise_values.append(r_val)
                frown_values.append(f_val)

                # --- 4. EMOTION (ONNX) ---
                if self.has_emotion_net and stats["frames_analyzed"] % 5 == 0:
                    emotion = self._detect_emotion(image, results.multi_face_landmarks[0])
                    stats["emotion_counts"][emotion] += 1

        cap.release()

        # --- FINAL CALCULATIONS ---
        duration_sec = stats["frames_total"] / 30.0  # Assuming ~30fps
        if duration_sec == 0: duration_sec = 1
        duration_min = duration_sec / 60.0

        # Blink Rate
        blink_rate = stats["blinks"] / duration_min if duration_min > 0 else 0

        # Expressiveness Score (Standard Deviation)
        raise_std = np.std(raise_values) if raise_values else 0
        frown_std = np.std(frown_values) if frown_values else 0
        robot_score = min(((raise_std + frown_std) / 0.02) * 10, 10)

        # Dominant Emotion
        dominant_emotion = max(stats["emotion_counts"], key=stats["emotion_counts"].get)

        # Eye Contact % (Looking at Screen)
        eye_contact_pct = (stats["gaze"]["Screen"] / stats["frames_analyzed"]) * 100 if stats[
                                                                                            "frames_analyzed"] > 0 else 0

        return {
            "eye_contact_percent": int(eye_contact_pct),
            "gaze_breakdown": stats["gaze"],
            "blink_rate_per_min": round(blink_rate, 1),
            "blink_count": stats["blinks"],
            "expressiveness_score": round(robot_score, 1),
            "dominant_emotion": dominant_emotion,
            "emotion_breakdown": stats["emotion_counts"]
        }

    # --- HELPER METHODS ---

    def _euclidean_distance(self, p1, p2):
        x1, y1 = (p1.x, p1.y) if hasattr(p1, 'x') else (p1[0], p1[1])
        x2, y2 = (p2.x, p2.y) if hasattr(p2, 'x') else (p2[0], p2[1])
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def _get_ear(self, landmarks, indices):
        v1 = self._euclidean_distance(landmarks[indices[1]], landmarks[indices[5]])
        v2 = self._euclidean_distance(landmarks[indices[2]], landmarks[indices[4]])
        h = self._euclidean_distance(landmarks[indices[0]], landmarks[indices[3]])
        return (v1 + v2) / (2.0 * h) if h > 0 else 0

    def _get_brow_metrics(self, landmarks):
        # Scale Ref: Outer Eye Corners (133, 263)
        face_width = self._euclidean_distance(landmarks[133], landmarks[263])
        if face_width == 0: return 0, 0

        # Raise: Left Brow Mid (66) to Left Eye Top (159)
        raise_dist = self._euclidean_distance(landmarks[66], landmarks[159])

        # Frown: Left Brow Inner (107) to Right Brow Inner (336)
        frown_dist = self._euclidean_distance(landmarks[107], landmarks[336])

        return raise_dist / face_width, frown_dist / face_width

    def _get_gaze_direction(self, mesh_points, s_h, s_v):
        """Returns new smoothed H, smoothed V, and the Direction String"""
        eye_left, eye_right = mesh_points[33], mesh_points[133]
        eye_top, eye_bottom = mesh_points[159], mesh_points[145]
        iris = mesh_points[468]

        raw_h = np.linalg.norm(eye_left - iris) / np.linalg.norm(eye_left - eye_right)
        raw_v = np.linalg.norm(eye_top - iris) / np.linalg.norm(eye_top - eye_bottom)

        new_h = (raw_h * self.SMOOTHING) + (s_h * (1 - self.SMOOTHING))
        new_v = (raw_v * self.SMOOTHING) + (s_v * (1 - self.SMOOTHING))

        direction = "Screen"
        if not (self.H_MIN < new_h < self.H_MAX and self.V_MIN < new_v < self.V_MAX):
            if new_h < self.H_MIN:
                direction = "Right"
            elif new_h > self.H_MAX:
                direction = "Left"
            if new_v < self.V_MIN:
                direction = "Up"
            elif new_v > self.V_MAX:
                direction = "Down"

        return new_h, new_v, direction

    def _detect_emotion(self, image, landmarks):
        # ... (Same as before, cropping face and running ONNX) ...
        # For brevity, reusing the logic you already had in previous version.
        # If you need this code block again, let me know, but it should be standard.
        try:
            h, w, c = image.shape
            x_min = int(min([l.x for l in landmarks.landmark]) * w)
            x_max = int(max([l.x for l in landmarks.landmark]) * w)
            y_min = int(min([l.y for l in landmarks.landmark]) * h)
            y_max = int(max([l.y for l in landmarks.landmark]) * h)

            face = image[max(0, y_min - 20):min(h, y_max + 20), max(0, x_min - 20):min(w, x_max + 20)]
            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64))
            blob = cv2.dnn.blobFromImage(resized, 1.0, (64, 64), (0, 0, 0), swapRB=False, crop=False)
            self.emotion_net.setInput(blob)
            scores = self.emotion_net.forward()[0]
            softmax = np.exp(scores) / np.sum(np.exp(scores))
            return self.EMOTIONS[np.argmax(softmax)]
        except:
            return "Neutral"