import cv2
from deepface import DeepFace
import numpy as np

# Load the Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(0)

        # Variables to optimize performance
        self.frame_count = 0  # Counter to skip frames
        self.current_emotion = "Analyzing..."  # Store the last calculated emotion

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None

        # 1. Detect Face
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)

        for (x, y, w, h) in faces:
            # Draw the box
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # 2. EMOTION ANALYSIS (Optimization Logic)
            # Only run the heavy AI model every 10 frames (approx every 0.3 seconds)
            if self.frame_count % 10 == 0:
                try:
                    # Crop out just the face
                    face_roi = image[y:y + h, x:x + w]

                    # Analyze it!
                    # actions=['emotion']: We only want emotion, not age/gender (faster)
                    # enforce_detection=False: Prevents crash if the cut-out face is weird
                    result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)

                    # Update the current emotion variable
                    # DeepFace returns a list, so we take the first result
                    self.current_emotion = result[0]['dominant_emotion']

                except Exception as e:
                    print(f"Error in analysis: {e}")

            # 3. Display the Emotion Label
            # We use self.current_emotion (which updates every 10 frames)
            cv2.putText(image, self.current_emotion, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36, 255, 12), 2)

        self.frame_count += 1

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()