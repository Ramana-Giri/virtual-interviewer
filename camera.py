import cv2


class VideoCamera(object):
    def __init__(self):
        # Open the default camera (0)
        self.video = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None

        # --- PLACEHOLDER FOR EMOTION DETECTION ---
        # Later, we will send 'image' to our AI model here.
        # For now, let's just draw a rectangle to prove OpenCV is working.
        cv2.rectangle(image, (100, 100), (400, 400), (0, 255, 0), 2)
        # -----------------------------------------

        # Encode the frame to JPEG format for the browser
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()