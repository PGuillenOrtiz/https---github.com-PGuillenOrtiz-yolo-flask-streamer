from flask import Response
import cv2
from app.camera import VideoCamera

class Detector:
    def __init__(self):
        self.camera = VideoCamera()

    def generate_frames(self):
        while True:
            frame = self.camera.get_frame()
            if frame is None:
                break
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n') 

    def stream(self):
        return Response(self.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')