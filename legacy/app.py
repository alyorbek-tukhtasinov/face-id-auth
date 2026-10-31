import cv2
import numpy as np
import mediapipe as mp
import face_recognition
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import pyttsx3
import threading
import time
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
known_images = ["Alyorbek.jpg"]
known_encodings = []
for img_path in known_images:
    known_image = cv2.imread(img_path)
    if known_image is None:
        print(f"Error loading image: {img_path}")
        continue
    known_image = cv2.cvtColor(known_image, cv2.COLOR_BGR2RGB)
    known_encodings.append(face_recognition.face_encodings(known_image)[0])
root = tk.Tk()
root.title("Alyorbekning Face ID loyiha ishi")
root.geometry("900x700")
root.configure(bg="#f4f4f9")
engine = pyttsx3.init()
voices = engine.getProperty('voices')
for voice in voices:
    if "zira" in voice.name.lower():
        engine.setProperty('voice', voice.id)
        break
engine.setProperty('rate', 150)
def speak(text):
    engine.say(text)
    engine.runAndWait()
title_label = tk.Label(root, text="Yuzni aniqlash va hayotiylikni tekshirish dasturi", font=("Arial", 18, "bold"), bg="#f4f4f9")
title_label.pack(pady=20)
status_label = tk.Label(root, text="Kamera o'chiq!", font=("Arial", 14), bg="#f4f4f9", fg="#333333")
status_label.pack(pady=10)
progress = ttk.Progressbar(root, length=300, mode="indeterminate")
progress.pack(pady=20)
background_image = Image.open("C:\\Users\\HP\\OneDrive\\Desktop\\individual\\bg.jpg") 
background_image = background_image.resize((640, 480))  
background_photo = ImageTk.PhotoImage(background_image)
canvas = tk.Canvas(root, width=640, height=480, bg="#ffffff")
canvas.create_image(0, 0, image=background_photo, anchor=tk.NW)
canvas.image = background_photo 
canvas.pack(pady=20)
stage = "right" 
right_done = False
left_done = False
straight_done = False
welcome_label = None 
final_message_spoken = False
def update_status(message):
    status_label.config(text=message)
def detect_head_turn(face_landmarks):
    nose_tip = face_landmarks.landmark[1]
    left_cheek = face_landmarks.landmark[234]
    right_cheek = face_landmarks.landmark[454]
    if nose_tip.x > right_cheek.x:
        return "Left Turn"
    elif nose_tip.x < left_cheek.x:
        return "Right Turn"
    else:
        return "Center"
def show_frame(frame):
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_pil = Image.fromarray(frame_rgb)
    frame_tk = ImageTk.PhotoImage(image=frame_pil)
    canvas.create_image(0, 0, image=frame_tk, anchor=tk.NW)
    canvas.image = frame_tk
def camera_loop():
    global stage, right_done, left_done, straight_done, welcome_label, final_message_spoken
    progress.start()
    update_status("Kamera ishga tushmoqda...")
    time.sleep(5)
    speak("Please turn your head to the right.")
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("Failed to read from camera!")
            break
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                head_turn = detect_head_turn(face_landmarks)
                if stage == "right" and head_turn == "Right Turn":
                    right_done = True
                    stage = "left"
                    speak("Please turn your head to the left.")
                elif stage == "left" and head_turn == "Left Turn":
                    left_done = True
                    stage = "straight"
                    speak("Please look straight ahead.")
                elif stage == "straight" and head_turn == "Center":
                    straight_done = True
                    stage = "done"
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
            name = "Unknown"
            if True in matches:
                name = "Matched"
            if stage == "done" and not final_message_spoken:
                if right_done and left_done and straight_done:
                    if name == "Matched":
                        update_status("Yuz tanildi - Face ID muvaffaqiyatli!")
                        speak("Face recognized and liveness detected successfully!")
                        final_message_spoken = True
                        if welcome_label:
                            welcome_label.destroy()
                        welcome_label = tk.Label(root, text="Welcome, Alyorbek!", font=("Arial", 16, "bold"), fg="#4CAF50", bg="#f4f4f9")
                        welcome_label.pack(pady=20)
                        return
                    else:
                        update_status("Yuz tanilmadi - Face ID muvaffaqiyatsiz!")
                        speak("Face not recognized. Liveness check failed!")
                        final_message_spoken = True
                        return
                else:
                    update_status("Liveness check not successful!")
        show_frame(frame)
        if cv2.waitKey(3) & 0xFF == ord('q'):
            break
    progress.stop()
def start_camera():
    threading.Thread(target=camera_loop, daemon=True).start()
start_button = tk.Button(root, text="Kamerani yoqish", font=("Arial", 14), command=start_camera, bg="#4CAF50", fg="white", relief="raised", width=20)
start_button.pack(pady=20)
start_button.config(activebackground="#45a049")
root.mainloop()
