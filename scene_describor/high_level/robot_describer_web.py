import time
import sys
import threading
from flask import Flask, render_template, Response
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.go2.video.video_client import VideoClient
import cv2
import numpy as np
import mediapipe as mp
from ollama import generate

app = Flask(__name__)
description = ""

class SportModeTest:
    def __init__(self) -> None:
        self.px0 = 0
        self.py0 = 0
        self.yaw0 = 0

        self.client = SportClient()  # Create a sport client
        self.client.SetTimeout(10.0)
        self.client.Init()

    def GetInitState(self, robot_state: SportModeState_):
        self.px0 = robot_state.position[0]
        self.py0 = robot_state.position[1]
        self.yaw0 = robot_state.imu_state.rpy[2]

    def StandUp(self):
        self.client.StandUp()
        print("Stand up !!!")
        time.sleep(1)

    def StandDown(self):
        self.client.StandDown()
        print("Stand down !!!")
        time.sleep(1)

# Robot state
robot_state = unitree_go_msg_dds__SportModeState_()
def HighStateHandler(msg: SportModeState_):
    global robot_state
    robot_state = msg

def get_description(image_content):
    global description
    prompt = "Describe the scene."
    responses = generate('llava:7b', prompt, images=[image_content], stream=True)
    
    description = ""
    for response in responses:
        description += response['response']
    
    return description

def generate_video():
    global description
    client = VideoClient()  # Create a video client
    client.SetTimeout(3.0)
    client.Init()

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.5)
    mp_drawing = mp.solutions.drawing_utils

    code, data = client.GetImageSample()

    while code == 0:
        code, data = client.GetImageSample()
        if code != 0:
            break

        image_data = np.frombuffer(bytes(data), dtype=np.uint8)
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result = hands.process(image_rgb)

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
                thumb_ip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_IP]
                thumb_state = 'down' if thumb_tip.y > thumb_ip.y else 'up'

                if thumb_state == 'up':
                    test.StandUp()
                elif thumb_state == 'down':
                    test.StandDown()

        resized_frame = cv2.resize(image, (480, 360))
        _, buffer = cv2.imencode('.jpg', resized_frame)
        image_content = buffer.tobytes()

        description = get_description(image_content)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(resized_frame, description, (10, 30), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        ret, jpeg = cv2.imencode('.jpg', resized_frame)
        frame = jpeg.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

    if code != 0:
        print("Get image sample error. code:", code)
    else:
        cv2.imwrite("front_image.jpg", image)

    cv2.destroyWindow("front_camera")
    hands.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/description')
def description_feed():
    global description
    return description

def start_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ChannelFactoryInitialize(0, sys.argv[1])
    else:
        ChannelFactoryInitialize(0)
        
    sub = ChannelSubscriber("rt/sportmodestate", SportModeState_)
    sub.Init(HighStateHandler, 10)
    time.sleep(1)

    test = SportModeTest()
    test.GetInitState(robot_state)

    print("Start test !!!")

    flask_thread = threading.Thread(target=start_flask)
    flask_thread.start()

    while True:
        time.sleep(1)
