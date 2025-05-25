# Drowsiness and Yawn Detection System

A real-time drowsiness and yawn detection system using Python, OpenCV, MediaPipe FaceMesh (via CVZone), and optional Arduino integration. This project plays a warning sound and logs events when it detects signs of sleepiness or yawning.

---

## 🧠 Features
- Eye Aspect Ratio (EAR)–based drowsiness detection
- Mouth Aspect Ratio (MAR)–based yawn detection
- Alarm system with sound notification
- Visual indicator (Green/Yellow/Red) for live EAR/MAR status
- Logging to CSV with timestamps and event duration
- Optional hardware control via Arduino (e.g., buzzer/LED)

---

## 📦 Requirements
- Python **3.8**
- CvZone 
- Mediapipe
- Pyglet (for sound)
- PyFirmata (for Arduino communication)

```bash
pip install opencv-python cvzone pyglet pyfirmata
```

---

## 🚀 How to Run
1. Connect a webcam.
2. Run the script:
```bash
python drowsiness_detection.py
```
3. A window will appear showing the video feed and current EAR/MAR values.
4. The system will:
   - Trigger sound and alert box if drowsiness or yawning is detected.
   - Record the event to `database.csv` with timestamp and duration.

---

## 🔊 EAR/MAR Thresholds (default)
| Indicator        | EAR         | MAR         | Description                      |
|------------------|-------------|-------------|----------------------------------|
| ✅ Normal        | > 0.23      | < 0.65      | Awake                            |
| ⚠️ Warning       | < 0.23      | -           | Eye closing begins               |
| 🔴 Drowsy/Yawning| < 0.23 (40+ frames) | > 0.65 (40+ frames) | Alert triggered         |

---

## 🔧 Arduino Configuration (Optional)
If you wish to control hardware like a buzzer or LED when drowsiness is detected:

1. Open **Arduino IDE**
2. Go to:
   - **File → Examples → Firmata → StandardFirmata**
   - **Tools → Board → Arduino/Genuino Uno**
   - **Tools → Port → Select the correct COM port**
3. Click **Upload** to flash the StandardFirmata sketch.

In the Python script:
```python
# pin = 7
# port = "COM7"
# board = pyfirmata.Arduino(port)
# board.digital[pin].write(1)  # HIGH (initial state)
```

Uncomment and modify these lines to match your port and pin.

---

## 📁 Log Format
Events are saved in `database.csv` as:
```
Date/Time, Condition, Duration
18-05-2025 16:42:12, Sleep, 3.82s
```

---

## 📷 Credits
- [MediaPipe FaceMesh](https://google.github.io/mediapipe/solutions/face_mesh.html)
- [CVZone](https://github.com/cvzone/cvzone)

---

## 🛠 Future Enhancements (Ideas)
- Real-time graph of EAR/MAR
- GUI overlay or dashboard
- Blinking frequency analysis
- Multi-user detection

---

## 👨‍💻 Author
Crafted with attention by fsalll. Contributions welcome!
