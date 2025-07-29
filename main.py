import os
import sys

# Set OpenCV to use headless mode
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

try:
    import cv2
    print(f"OpenCV version: {cv2.__version__}")
except ImportError as e:
    print(f"Failed to import OpenCV: {e}")
    sys.exit(1)

from flask import Flask, render_template, Response
from camera import VideoCamera
import cv2
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index1.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(VideoCamera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
