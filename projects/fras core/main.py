from flask import Flask, send_file, render_template
import cv2
import csv
import datetime
import os
import threading
import queue
import numpy as np
import time
from insightface.app import FaceAnalysis

app = Flask(__name__)

# Configurations
KNOWN_FACES_FOLDER = "input_images"
CSV_FILE = "recognized_faces.csv"
RTSP_URL = "rtsp://admin:VUCIHS@192.168.0.100:554/"  # Update with actual RTSP URL
USE_WEBCAM = True
FRAME_SKIP = 5  # Adjust for performance
UPSCALE_SIZE = (112, 112)  # ArcFace recommended size

# Initialize FaceAnalysis for face detection & recognition
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(640, 640))

# Load known faces
known_face_encodings = []
known_face_names = []

for filename in os.listdir(KNOWN_FACES_FOLDER):
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_path = os.path.join(KNOWN_FACES_FOLDER, filename)
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        faces = face_app.get(img)

        if faces:
            face_img = img[int(faces[0].bbox[1]):int(faces[0].bbox[3]),
                           int(faces[0].bbox[0]):int(faces[0].bbox[2])]
            face_img = cv2.resize(face_img, UPSCALE_SIZE)
            face_embedding = faces[0].normed_embedding
            known_face_encodings.append(face_embedding)
            known_face_names.append(os.path.splitext(filename)[0])

# Attendance records
latest_attendance = {}
is_attendance_running = False
video_capture = None
frame_queue = queue.Queue(maxsize=10)

def update_csv():
    """Update the CSV file with the latest timestamps."""
    with open(CSV_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Name", "Timestamp"])
        writer.writeheader()
        for name, timestamp in latest_attendance.items():
            writer.writerow({"Name": name, "Timestamp": timestamp})

def capture_frames():
    """Continuously capture frames and store them in a queue for processing."""
    global video_capture

    if USE_WEBCAM:
        print("🎥 Using local webcam...")
        video_capture = cv2.VideoCapture(0)  # Default webcam
    else:
        print("🌐 Using RTSP stream...")
        video_capture = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        video_capture.set(cv2.CAP_PROP_FPS, 15)
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while is_attendance_running:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            if USE_WEBCAM:
                print("⚠️ Webcam not available, retrying...")
                time.sleep(2)
                video_capture.release()
                video_capture = cv2.VideoCapture(0)
            else:
                print("⚠️ Lost connection to RTSP stream. Reconnecting...")
                video_capture.release()
                time.sleep(2)
                video_capture = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
            continue

        if not frame_queue.full():
            frame_queue.put(frame)

def process_frames():
    """Process frames from queue and perform face recognition."""
    global is_attendance_running

    while is_attendance_running:
        if frame_queue.empty():
            continue

        frame = frame_queue.get()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_app.get(frame_rgb)

        for face in faces:
            x1, y1, x2, y2 = map(int, face.bbox)
            face_img = frame_rgb[y1:y2, x1:x2]
            face_img = cv2.resize(face_img, UPSCALE_SIZE)

            # Face Recognition
            name = "Unknown"
            face_embedding = face.normed_embedding

            if known_face_encodings:
                similarities = np.dot(known_face_encodings, face_embedding)
                best_match_index = np.argmax(similarities)

                if similarities[best_match_index] > 0.5:
                    name = known_face_names[best_match_index]

            # Mark attendance
            latest_attendance[name] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_csv()

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start-attendance')
def start_attendance():
    global is_attendance_running
    if not is_attendance_running:
        is_attendance_running = True
        threading.Thread(target=capture_frames, daemon=True).start()
        threading.Thread(target=process_frames, daemon=True).start()
        return "Attendance started."
    return "Attendance is already running."

@app.route('/stop-attendance')
def stop_attendance():
    global is_attendance_running
    is_attendance_running = False
    return "Attendance stopped."

@app.route('/download-attendance')
def download_attendance():
    return send_file(CSV_FILE, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5500)
