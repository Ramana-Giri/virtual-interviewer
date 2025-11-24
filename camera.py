import cv2

# Load the face detector (Haar Cascade) provided by OpenCV
# This file comes pre-installed with the opencv-python library
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

class VideoCamera(object):
    def __init__(self):
        # Open the default camera
        self.video = cv2.VideoCapture(0)

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None

        # 1. Convert to Grayscale
        # Face detection works faster and better on grayscale images
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 2. Detect Faces
        # scaleFactor=1.1: Reduces image size by 10% each pass to find faces of different sizes
        # minNeighbors=4: Higher value = fewer false positives (less random boxes)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)

        # 3. Draw Rectangle around the faces
        # (x, y) is the top-left corner, (w, h) is width and height
        for (x, y, w, h) in faces:
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 4. Encode the frame
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()