import cv2
import pyglet.media
from cvzone.FaceMeshModule import FaceMeshDetector
import pyfirmata
import csv
from datetime import datetime
import time

# Inisialisasi kamera
cap = cv2.VideoCapture(0)
cap.set(3, 1280)
cap.set(4, 720)

# Inisialisasi FaceMesh
detector = FaceMeshDetector(maxFaces=1)

# Threshold dan counter
EAR_THRESH = 0.23
EAR_CONSEC_FRAMES = 40
MAR_THRESH = 0.65
MAR_CONSEC_FRAMES = 40

breakcount_s, breakcount_y = 0, 0
counter_s, counter_y = 0, 0
state_s, state_y = False, False
sleep_start_time = None
yawn_start_time = None

# Load Sound
sound = pyglet.media.load("alarm.wav", streaming=False)

# Setup Arduino
# pin = 7
# port = "COM7"
# board = pyfirmata.Arduino(port)
# board.digital[pin].write(1)

# EAR and MAR landmarks
left_eye_indices = [33, 160, 158, 133, 153, 144]
right_eye_indices = [362, 385, 387, 263, 373, 380]
mar_points = [61, 81, 13, 311, 308, 402, 14, 178]
faceId = left_eye_indices + right_eye_indices + mar_points

# EAR Function

def calculate_EAR(eye_points, face):
    vert1, _ = detector.findDistance(face[eye_points[1]], face[eye_points[5]])
    vert2, _ = detector.findDistance(face[eye_points[2]], face[eye_points[4]])
    hor, _ = detector.findDistance(face[eye_points[0]], face[eye_points[3]])
    EAR = (vert1 + vert2) / (2.0 * hor)
    return EAR

# MAR Function
def calculate_MAR(mar_pts, face):
    vert1, _ = detector.findDistance(face[mar_pts[1]], face[mar_pts[7]])
    vert2, _ = detector.findDistance(face[mar_pts[2]], face[mar_pts[6]])
    vert3, _ = detector.findDistance(face[mar_pts[3]], face[mar_pts[5]])
    hor, _ = detector.findDistance(face[mar_pts[0]], face[mar_pts[4]])
    MAR = (vert1 + vert2 + vert3) / (2.0 * hor)
    return MAR

# Alert Function
def alert():
    cv2.rectangle(img, (0, img.shape[0] // 2 - 40), (img.shape[1], img.shape[0] // 2 + 40), (0, 0, 255), cv2.FILLED)
    text = "PERINGATAN MENGANTUK!!!"
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_PLAIN, 3, 2)[0]
    text_x = (img.shape[1] - text_size[0]) // 2
    text_y = img.shape[0] // 2 + 20
    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 255), 2)

# Data recording function
def recordData(condition, start_time):
    with open("database.csv", "a", newline="") as file:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        now = datetime.now()
        dtString = now.strftime("%d-%m-%Y %H:%M:%S")
        writer = csv.writer(file)
        writer.writerow((dtString, condition, f"{duration}s"))

# Main
while True:
    success, img = cap.read()
    img = cv2.flip(img, 1)

    img, faces = detector.findFaceMesh(img, draw=False)

    if faces:
        face = faces[0]

        # Calculate EAR and MAR
        left_EAR = calculate_EAR(left_eye_indices, face)
        right_EAR = calculate_EAR(right_eye_indices, face)
        avg_EAR = (left_EAR + right_EAR) / 2

        mar = calculate_MAR(mar_points, face)

        # Status indicator color
        status_color = (0, 255, 0)  # default: green (safe)
        if avg_EAR < EAR_THRESH:
            status_color = (0, 255, 255)  # yellow: starting to feel sleepy
        if breakcount_s >= EAR_CONSEC_FRAMES or breakcount_y >= MAR_CONSEC_FRAMES:
            status_color = (0, 0, 255)  # red: alarm active

        # Show EAR & MAR values
        cv2.putText(img, f'EAR: {avg_EAR:.2f}', (10, 30), cv2.FONT_HERSHEY_PLAIN, 2, status_color, 2)
        cv2.putText(img, f'MAR: {mar:.2f}', (10, 60), cv2.FONT_HERSHEY_PLAIN, 2, status_color, 2)

        # Show counters
        cv2.putText(img, f'Sleep Count: {counter_s}', (10, img.shape[0] - 60), cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)
        cv2.putText(img, f'Yawn Count: {counter_y}', (10, img.shape[0] - 30), cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)

        # Drowsiness detection (EAR)
        if avg_EAR < EAR_THRESH:
            if sleep_start_time is None:
                sleep_start_time = time.time()
            breakcount_s += 1
            if breakcount_s >= EAR_CONSEC_FRAMES:
                alert()
                if not state_s:
                    counter_s += 1
                    sound.play()
                    # board.digital[pin].write(0)
                    recordData("Sleep", sleep_start_time)
                    state_s = True
        else:
            breakcount_s = 0
            sleep_start_time = None
            if state_s:
                # board.digital[pin].write(1)
                state_s = False

        # Yawn detection (MAR)
        if mar > MAR_THRESH:
            if yawn_start_time is None:
                yawn_start_time = time.time()
            breakcount_y += 1
            if breakcount_y >= MAR_CONSEC_FRAMES:
                alert()
                if not state_y:
                    counter_y += 1
                    sound.play()
                    # board.digital[pin].write(0)
                    recordData("Yawn", yawn_start_time)
                    state_y = True
        else:
            breakcount_y = 0
            yawn_start_time = None
            if state_y:
                # board.digital[pin].write(1)
                state_y = False

        # Dots
        for id in faceId:
            cv2.circle(img, face[id], 3, status_color, cv2.FILLED)

    cv2.imshow("Sample", img)
    cv2.waitKey(1)