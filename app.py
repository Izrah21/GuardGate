import os
import time
import logging
import uuid
import cv2
import numpy as np
from flask import Flask, render_template_string, Response, request, jsonify, redirect, url_for, session
from supabase import create_client, Client

# Import blueprint galing sa guard.py
from guard import guard_bp

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = 'super-secret-key-please-change'

# I-register ang guard_bp para ma-call ang guard.py sa port 5000
app.register_blueprint(guard_bp)

ERROR_LOG_FILE = "guardgate_errors.log"
FACE_DIR = "captured_faces"

logging.basicConfig(
    filename=ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

os.makedirs(FACE_DIR, exist_ok=True)

recognizer = cv2.face.LBPHFaceRecognizer_create()
visitor_map = {}
is_trained = False
cooldown_timer = 0
current_unrecognized_frame = None

# Timer delay configuration (2.5 seconds hold before triggering Time In/Out)
VERIFICATION_DELAY = 2.5
detected_face_start_time = None
current_verifying_id = None
last_face_seen_time = 0

system_status = {
    "text": "System Active: Scanning for registered visitors...", 
    "status": "normal",
    "unknown_detected": False,
    "face_detected": False
}

script_dir = os.path.dirname(os.path.abspath(__file__))
cascade_path = os.path.join(script_dir, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(cascade_path)

def load_recognizer_training():
    global visitor_map, is_trained, recognizer
    visitor_map = {}
    faces_train = []
    ids_train = []
    current_id = 0

    try:
        response = supabase.table("visitors").select("*").execute()
        visitors = response.data

        if not visitors:
            is_trained = False
            return

        for row in visitors:
            s_id = row["student_id"]
            img_name = f"{s_id}.jpg"
            local_img_path = os.path.join(FACE_DIR, img_name)

            if not os.path.exists(local_img_path):
                try:
                    res = supabase.storage.from_("faces").download(img_name)
                    with open(local_img_path, "wb") as f:
                        f.write(res)
                except Exception as ex:
                    logging.error(f"Failed to download image for {s_id}: {ex}")
                    continue

            if os.path.exists(local_img_path):
                img = cv2.imread(local_img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    faces_train.append(cv2.resize(img, (200, 200)))
                    ids_train.append(current_id)
                    visitor_map[current_id] = {
   "Student_ID": s_id,
   "Name": row["normalized_name"],
   "College": row["college"],
   "Course": row["course_year"]
                    }
                    current_id += 1

        if faces_train:
            recognizer.train(faces_train, np.array(ids_train))
            is_trained = True
        else:
            is_trained = False
    except Exception as e:
        logging.error(f"Error loading training data from Supabase: {e}")
        is_trained = False

load_recognizer_training()

def process_auto_attendance(visitor):
    global cooldown_timer, system_status
    s_id = visitor["Student_ID"]
    name = visitor["Name"]
    college = visitor["College"]
    course = visitor["Course"]

    try:
        logs_res = supabase.table("logs").select("*").eq("student_id", s_id).execute()
        user_logs = logs_res.data

        action = "Time In"
        if user_logs and user_logs[-1]["action"] == "Time In":
            action = "Time Out"

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        supabase.table("logs").insert({
            "student_id": s_id,
            "normalized_name": name,
            "college": college,
            "course_year": course,
            "action": action,
            "timestamp": timestamp
        }).execute()

        system_status["text"] = f"SUCCESS ({action}): {name} | ID: {s_id}"
        system_status["status"] = "success"
        system_status["unknown_detected"] = False
        
        cooldown_timer = time.time() + 5
    except Exception as e:
        logging.error(f"Error processing attendance in Supabase: {e}")

def generate_frames():
    global current_unrecognized_frame, system_status, cooldown_timer
    global detected_face_start_time, current_verifying_id, last_face_seen_time

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    while True:
        success, frame = cap.read()
        if not success:
            break

        display_frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(display_frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

        current_time = time.time()
        has_face = len(faces) > 0
        system_status["face_detected"] = has_face

        if has_face:
            last_face_seen_time = current_time
            (x, y, w, h) = faces[0]
            face_roi = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            current_unrecognized_frame = display_frame.copy()

            if is_trained:
                label_id, confidence = recognizer.predict(face_roi)
                if confidence < 100 and label_id in visitor_map:
                    visitor = visitor_map[label_id]
                    visitor_id = visitor["Student_ID"]
                    visitor_first_name = visitor["Name"].split(",")[0]

                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (34, 197, 94), 2)

                    if current_time < cooldown_timer:
                        detected_face_start_time = None
                        current_verifying_id = None
                        cv2.putText(display_frame, f"{visitor_first_name} (Recorded)", (x, max(25, y - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (34, 197, 94), 2)
                    else:
                        if current_verifying_id != visitor_id or detected_face_start_time is None:
                            current_verifying_id = visitor_id
                            detected_face_start_time = current_time

                        elapsed = current_time - detected_face_start_time
                        remaining = max(0.0, VERIFICATION_DELAY - elapsed)

                        if elapsed < VERIFICATION_DELAY:
                            progress = min(1.0, elapsed / VERIFICATION_DELAY)
                            bar_w = int(w * progress)
                            cv2.rectangle(display_frame, (x, y + h + 8), (x + w, y + h + 15), (40, 40, 40), -1)
                            cv2.rectangle(display_frame, (x, y + h + 8), (x + bar_w, y + h + 15), (34, 197, 94), -1)
                            cv2.putText(display_frame, f"Hold still: {remaining:.1f}s", (x, max(25, y - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (34, 197, 94), 2)

                            system_status["text"] = f"Face Detected: {visitor['Name']} : Hold still ({remaining:.1f}s)..."
                            system_status["status"] = "verifying"
                            system_status["unknown_detected"] = False
                        else:
                            process_auto_attendance(visitor)
                            detected_face_start_time = None
                            current_verifying_id = None
                else:
                    detected_face_start_time = None
                    current_verifying_id = None
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (225, 29, 72), 2)
                    cv2.putText(display_frame, "Unrecognized", (x, max(25, y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (225, 29, 72), 2)
                    system_status["text"] = "Unrecognized Face Detected : Please Register"
                    system_status["status"] = "error"
                    system_status["unknown_detected"] = True
            else:
                detected_face_start_time = None
                current_verifying_id = None
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (245, 158, 11), 2)
                system_status["text"] = "Database is empty. Please register your face."
                system_status["status"] = "warning"
                system_status["unknown_detected"] = True
        else:
            if current_time - last_face_seen_time > 0.6:
                detected_face_start_time = None
                current_verifying_id = None

            if not system_status["unknown_detected"] and current_time > cooldown_timer + 2:
                system_status["text"] = "System Active: Scanning for registered visitors..."
                system_status["status"] = "normal"
                system_status["unknown_detected"] = False

        ret, buffer = cv2.imencode('.jpg', display_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GuardGate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* Lock the page to the viewport: no root or body scrolling */
        html, body {
            height: 100%;
            width: 100%;
            margin: 0;
            overflow: hidden;
        }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%);
        }
        .app-root {
            height: 100vh;
            height: 100dvh;
            width: 100vw;
            overflow: hidden;
        }
        /* Card width is derived from available height so a 16:9 camera never overflows the screen */
        .scanner-card {
            width: min(100%, 48rem, max(16rem, calc((100dvh - 13rem) * 16 / 9)));
        }
        @media (max-height: 520px) {
            .hide-short { display: none; }
        }
    </style>
</head>
<body class="text-slate-800 antialiased overflow-hidden">

    <!-- FLOATING TOAST NOTIFICATION CONTAINER (Eliminates 'localhost says' alerts) -->
    <div id="toast-container" class="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 pointer-events-none max-w-sm w-full"></div>

    <div class="app-root flex flex-col">

        <!-- HEADER -->
        <header class="shrink-0 px-4 sm:px-8 py-3 border-b border-emerald-900/10 bg-white/60 backdrop-blur flex items-center">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md shadow-emerald-800/15 shrink-0">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                </div>
                <div class="min-w-0">
                    <div class="flex items-center gap-2">
                        <h1 class="text-xl sm:text-2xl font-bold text-emerald-950 tracking-tight leading-tight">GuardGate</h1>
                    </div>
                    
                </div>
            </div>
        </header>

        <!-- MAIN SCANNER CONTAINER -->
        <main class="flex-1 min-h-0 flex items-center justify-center p-3 sm:p-5">
            <div class="scanner-card max-h-full flex flex-col bg-white rounded-2xl shadow-lg shadow-emerald-900/5 border border-emerald-900/10 overflow-hidden">
                <div class="shrink-0 px-4 sm:px-5 py-3 border-b border-emerald-900/5 bg-emerald-50/40 flex justify-between items-center gap-2">
                    <span class="text-xs font-semibold uppercase tracking-wider text-emerald-900 flex items-center gap-2 min-w-0">
                        <svg class="w-4 h-4 text-emerald-700 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        <span class="truncate">Live Face Recognition Scanner</span>
                    </span>
                    <span class="shrink-0 text-[11px] font-medium text-emerald-800 bg-emerald-100/70 px-2.5 py-0.5 rounded-full">
                        Auto Timer: 2.5s Hold
                    </span>
                </div>

                <!-- SCANNER VIEWPORT -->
                <div id="camera-container" class="relative bg-slate-900 w-full aspect-video min-h-0 flex justify-center items-center overflow-hidden transition-all duration-500 ease-in-out max-h-[600px] opacity-100 scale-100">
                    <img src="{{ url_for('video_feed') }}" class="object-cover h-full w-full opacity-95">

                    <!-- REGISTER BUTTON -->
                    <button id="register-btn" onclick="openModal()" class="hidden absolute bottom-4 sm:bottom-6 left-1/2 transform -translate-x-1/2 bg-white/95 backdrop-blur-md text-emerald-800 font-semibold text-xs py-2.5 sm:py-3 px-6 sm:px-8 rounded-full shadow-[0_8px_30px_rgb(0,0,0,0.2)] border border-emerald-200/80 hover:bg-emerald-50 hover:scale-105 transition-all duration-200 ease-out z-10 flex items-center gap-2 whitespace-nowrap">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
                        Register New Visitor
                    </button>
                </div>

                <!-- STANDBY OVERLAY -->
                <div id="standby-container" class="hidden w-full aspect-video min-h-0 p-6 text-center bg-slate-900 text-slate-400 flex flex-col items-center justify-center gap-3 overflow-hidden">
                    <div class="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-950/60 border border-emerald-800/30 text-emerald-400">
                        <svg class="w-6 h-6 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    </div>
                    <p class="text-sm font-semibold text-slate-200">Scanner on Standby</p>
                    <p class="hide-short text-xs text-slate-400 max-w-xs">Step in front of the scanner to activate the camera and verify attendance.</p>
                </div>

                <!-- STATUS PANEL -->
                <div id="status-panel" class="shrink-0 px-4 py-3 text-center text-sm font-medium text-emerald-800 bg-emerald-50/50 border-t border-emerald-900/10 transition-colors duration-300">
                    System Active: Scanning for registered visitors...
                </div>
            </div>
        </main>
    </div>

    <!-- REGISTRATION MODAL -->
    <div id="reg-modal" class="hidden fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 transition-opacity duration-300 overflow-hidden">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[94vh] max-h-[94dvh] flex flex-col overflow-hidden border border-emerald-900/15 relative">
            
            <!-- MODAL HEADER -->
            <div class="shrink-0 px-6 py-4 border-b border-emerald-900/10 flex justify-between items-center bg-emerald-50/60">
                <div class="flex items-center gap-2.5">
                    <div class="w-8 h-8 rounded-lg bg-emerald-700 text-white flex items-center justify-center">
   <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                    </div>
                    <div>
   <h2 class="text-base font-bold text-emerald-950">New Visitor Registration</h2>
   <p class="text-[11px] text-emerald-800/70 font-medium">Select your category to configure required details</p>
                    </div>
                </div>
                <button type="button" onclick="closeModal()" class="text-slate-400 hover:text-slate-700 transition-colors rounded-xl p-1.5 hover:bg-emerald-100/50">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            
            <!-- REGISTRATION FORM -->
            <form id="reg-form" onsubmit="submitRegistration(event)" class="p-4 sm:p-6 overflow-y-auto min-h-0 flex-1">
                
                <!-- USER TYPE SELECTOR (FIRST SELECTION) -->
                <div class="mb-6 p-4 rounded-xl bg-emerald-50/70 border border-emerald-200/80">
                    <label class="block text-xs font-bold uppercase tracking-wider text-emerald-900 mb-1.5 flex items-center gap-1.5">
   <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
   User Type <span class="text-rose-600">*</span>
                    </label>
                    <select id="user_type" name="user_type" onchange="handleUserTypeChange(this.value)" class="w-full border border-emerald-300 rounded-lg px-3.5 py-2.5 text-sm font-semibold bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm cursor-pointer">
   <option value="Student">Student</option>
   <option value="Parent">Parent</option>
   <option value="Faculty">Faculty</option>
   <option value="Others">Others</option>
                    </select>
                    <p id="user_type_hint" class="text-[11px] text-emerald-800/80 mt-1.5 font-medium">Standard student registration requiring Student ID and College.</p>
                </div>

                <!-- NAME FIELDS (COMMON TO ALL) -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Surname <span class="text-rose-600">*</span></label>
   <input type="text" name="surname" id="field_surname" required placeholder="e.g. Dela Cruz" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">First Name <span class="text-rose-600">*</span></label>
   <input type="text" name="fname" id="field_fname" required placeholder="e.g. Juan" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label id="label_mname" class="block text-xs font-semibold text-slate-700">Middle Name <span class="text-slate-400 font-normal">(Optional)</span></label>
   <input type="text" name="mname" id="field_mname" placeholder="e.g. Santos" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div id="group-suffix" class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Suffix</label>
   <select name="suffix" id="field_suffix" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm bg-white">
       <option value="N/A">N/A</option>
       <option value="Jr.">Jr.</option>
       <option value="Sr.">Sr.</option>
       <option value="III">III</option>
       <option value="IV">IV</option>
   </select>
                    </div>
                </div>

                <!-- STUDENT SECTION: ONLY COLLEGES IN DROPDOWN, STUDENT ID, COURSE & YEAR -->
                <div id="group-student" class="mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">College <span class="text-rose-600">*</span></label>
   <select name="college" id="field_college" required class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm bg-white cursor-pointer">
       <option value="" disabled selected>Select College...</option>
       <option value="CCIS">CCIS : College of Computing and Information Sciences</option>
       <option value="CAS">CAS : College of Arts and Sciences</option>
       <option value="COE">COE : College of Engineering</option>
       <option value="CBEA">CBEA : College of Business, Economics and Accountancy</option>
       <option value="CAFSD">CAFSD : College of Agriculture, Forestry and Sustainable Development</option>
       <option value="CHS">CHS : College of Health Sciences</option>
       <option value="COL">COL : College of Law</option>
       <option value="CASAT">CASAT : College of Aquatic Sciences and Applied Technology</option>
       <option value="CIT">CIT : College of Industrial Technology</option>
       <option value="CTE">CTE : College of Teacher Education</option>
   </select>
                    </div>
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Student ID <span class="text-rose-600">*</span></label>
   <input type="text" name="student_id" id="field_student_id" required placeholder="e.g. 22-1506" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Course & Year <span class="text-rose-600">*</span></label>
   <input type="text" name="course" id="field_course" required placeholder="e.g. BSCS - 3" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- PARENT SECTION: same grid as Student, no ID and no college (suffix is in the shared name fields) -->
                <div id="group-parent" class="hidden mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">Home / Residential Address <span class="text-rose-600">*</span></label>
   <input type="text" name="parent_address" id="field_parent_address" placeholder="e.g. Barangay 1, San Nicolas, Ilocos Norte" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- FACULTY SECTION: same grid as Student, no ID; College + Department -->
                <div id="group-faculty" class="hidden mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">College <span class="text-rose-600">*</span></label>
   <select name="faculty_college" id="field_faculty_college" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm bg-white cursor-pointer">
       <option value="" disabled selected>Select College...</option>
       <option value="CCIS">CCIS : College of Computing and Information Sciences</option>
       <option value="CAS">CAS : College of Arts and Sciences</option>
       <option value="COE">COE : College of Engineering</option>
       <option value="CBEA">CBEA : College of Business, Economics and Accountancy</option>
       <option value="CAFSD">CAFSD : College of Agriculture, Forestry and Sustainable Development</option>
       <option value="CHS">CHS : College of Health Sciences</option>
       <option value="COL">COL : College of Law</option>
       <option value="CASAT">CASAT : College of Aquatic Sciences and Applied Technology</option>
       <option value="CIT">CIT : College of Industrial Technology</option>
       <option value="CTE">CTE : College of Teacher Education</option>
   </select>
                    </div>
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">Department They Teach In <span class="text-rose-600">*</span></label>
   <input type="text" name="department" id="field_department" placeholder="e.g. Department of Computer Science" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- OTHERS SECTION: NAME FIELDS + ADDRESS/PURPOSE -->
                <div id="group-others" class="hidden mt-4 pt-4 border-t border-slate-100">
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Address or Purpose of Visit <span class="text-rose-600">*</span></label>
   <input type="text" name="other_address" id="field_other_address" placeholder="e.g. Guest / Delivery / Maintenance Inspection" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- IN-MODAL CONFIRMATION DIALOG (Avoids browser confirm()) -->
                <div id="cancel-confirm-box" class="hidden mt-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900">
                    <div class="flex items-start gap-3">
   <svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
   <div class="flex-1">
       <p class="text-xs font-bold">Discard entered information?</p>
       <p class="text-[11px] text-amber-800 mt-0.5">You have unsaved changes in the form. Are you sure you want to exit?</p>
       <div class="mt-3 flex items-center gap-2">
           <button type="button" onclick="dismissConfirmClose(true)" class="px-3 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg transition shadow-sm">
               Yes, Discard
           </button>
           <button type="button" onclick="dismissConfirmClose(false)" class="px-3 py-1.5 text-xs font-semibold text-amber-900 bg-white border border-amber-300 hover:bg-amber-100 rounded-lg transition shadow-sm">
               Keep Editing
           </button>
       </div>
   </div>
                    </div>
                </div>

                <!-- FORM BUTTONS -->
                <div class="sticky bottom-0 z-10 -mx-4 sm:-mx-6 -mb-4 sm:-mb-6 mt-6 px-4 sm:px-6 py-4 bg-white border-t border-slate-100 flex justify-end gap-3">
                    <button type="button" onclick="closeModal()" class="px-5 py-2.5 text-sm font-semibold text-slate-600 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition-colors shadow-sm">
   Cancel
                    </button>
                    <button id="submit-btn" type="submit" class="px-5 py-2.5 text-sm font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition-all shadow-sm flex items-center gap-2">
   <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
   Save
                    </button>
                </div>
            </form>
        </div>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        let noFaceSeconds = 0;
        let isCameraHidden = false;

        // Custom non-blocking toast notifications (Replaces window.alert - NO 'localhost says')
        function showToast(message, type = 'success', duration = 4000) {
            const container = document.getElementById('toast-container');
            if (!container) return;

            const toast = document.createElement('div');
            toast.className = 'pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-lg border transition-all duration-300 transform translate-y-2 opacity-0 text-sm font-medium';
            
            let iconSvg = '';
            if (type === 'success') {
                toast.className += ' bg-emerald-50 text-emerald-900 border-emerald-200 shadow-emerald-900/5';
                iconSvg = `<svg class="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
            } else if (type === 'error') {
                toast.className += ' bg-rose-50 text-rose-900 border-rose-200 shadow-rose-900/5';
                iconSvg = `<svg class="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`;
            } else if (type === 'warning') {
                toast.className += ' bg-amber-50 text-amber-900 border-amber-200 shadow-amber-900/5';
                iconSvg = `<svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
            } else {
                toast.className += ' bg-slate-50 text-slate-900 border-slate-200';
                iconSvg = `<svg class="w-5 h-5 text-slate-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
            }

            toast.innerHTML = `
                ${iconSvg}
                <div class="flex-1 text-xs leading-relaxed break-words">${message}</div>
                <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-slate-600 p-0.5 rounded-lg transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            `;

            container.appendChild(toast);
            requestAnimationFrame(() => {
                toast.classList.remove('translate-y-2', 'opacity-0');
                toast.classList.add('translate-y-0', 'opacity-100');
            });

            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-2');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        // Dynamic User Type Form Adjustment
        function handleUserTypeChange(type) {
            const studentGroup = document.getElementById('group-student');
            const parentGroup = document.getElementById('group-parent');
            const facultyGroup = document.getElementById('group-faculty');
            const othersGroup = document.getElementById('group-others');
            const suffixGroup = document.getElementById('group-suffix');
            const mnameInput = document.getElementById('field_mname');
            const mnameLabel = document.getElementById('label_mname');
            const hintText = document.getElementById('user_type_hint');

            // Hide all specialized field groups
            studentGroup.classList.add('hidden');
            parentGroup.classList.add('hidden');
            facultyGroup.classList.add('hidden');
            othersGroup.classList.add('hidden');

            // Reset required flags on dynamic inputs
            document.getElementById('field_student_id').required = false;
            document.getElementById('field_college').required = false;
            document.getElementById('field_course').required = false;
            document.getElementById('field_parent_address').required = false;
            document.getElementById('field_department').required = false;
            document.getElementById('field_faculty_college').required = false;
            document.getElementById('field_other_address').required = false;
            
            mnameInput.required = false;
            mnameLabel.innerHTML = 'Middle Name <span class="text-slate-400 font-normal">(Optional)</span>';

            if (type === 'Student') {
                studentGroup.classList.remove('hidden');
                suffixGroup.classList.remove('hidden');
                document.getElementById('field_student_id').required = true;
                document.getElementById('field_college').required = true;
                document.getElementById('field_course').required = true;
                hintText.innerText = 'Student registration requiring Student ID, College, and Course & Year.';
            } else if (type === 'Parent') {
                parentGroup.classList.remove('hidden');
                suffixGroup.classList.remove('hidden');
                mnameInput.required = true;
                mnameLabel.innerHTML = 'Middle Name <span class="text-rose-600">*</span>';
                document.getElementById('field_parent_address').required = true;
                hintText.innerText = 'Parent registration: requires Surname, First Name, Middle Name, and Address. Suffix is optional.';
            } else if (type === 'Faculty') {
                facultyGroup.classList.remove('hidden');
                suffixGroup.classList.remove('hidden');
                document.getElementById('field_faculty_college').required = true;
                document.getElementById('field_department').required = true;
                hintText.innerText = 'Faculty registration: requires Name fields, your College, and the Department you teach in.';
            } else if (type === 'Others') {
                othersGroup.classList.remove('hidden');
                suffixGroup.classList.remove('hidden');
                document.getElementById('field_other_address').required = true;
                hintText.innerText = 'Visitor / Guest registration: requires Name fields and Address/Purpose of visit.';
            }
        }

        // Live status poller
        function fetchStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const panel = document.getElementById('status-panel');
                    panel.innerText = data.text;
                    
                    let bgClass = 'bg-emerald-50/50', textClass = 'text-emerald-800', borderClass = 'border-emerald-900/10';
                    if (data.status === 'success') {
   bgClass = 'bg-emerald-100/90'; textClass = 'text-emerald-950 font-bold'; borderClass = 'border-emerald-300';
                    } else if (data.status === 'verifying') {
   bgClass = 'bg-emerald-100/60 animate-pulse'; textClass = 'text-emerald-900 font-semibold'; borderClass = 'border-emerald-300';
                    } else if (data.status === 'error') {
   bgClass = 'bg-rose-50'; textClass = 'text-rose-700 font-semibold'; borderClass = 'border-rose-200';
                    } else if (data.status === 'warning') {
   bgClass = 'bg-amber-50'; textClass = 'text-amber-800 font-semibold'; borderClass = 'border-amber-200';
                    }
                    
                    panel.className = `shrink-0 px-4 py-3 text-center text-sm font-medium transition-colors duration-300 border-t ${bgClass} ${textClass} ${borderClass}`;
                    
                    const regBtn = document.getElementById('register-btn');
                    if (data.unknown_detected) {
   regBtn.classList.remove('hidden');
                    } else {
   regBtn.classList.add('hidden');
                    }

                    handleCameraVisibility(data.face_detected);
                })
                .catch(() => {});
        }

        function handleCameraVisibility(faceDetected) {
            const cameraContainer = document.getElementById('camera-container');
            const standbyContainer = document.getElementById('standby-container');

            if (faceDetected) {
                noFaceSeconds = 0;

                if (isCameraHidden) {
                    isCameraHidden = false;
                    standbyContainer.classList.add('hidden');
                    cameraContainer.classList.remove('max-h-0', 'opacity-0', 'scale-95', 'pointer-events-none');
                    cameraContainer.classList.add('max-h-[600px]', 'opacity-100', 'scale-100');
                }
            } else {
                if (!isCameraHidden) {
                    noFaceSeconds++;

                    if (noFaceSeconds >= 5) {
   isCameraHidden = true;
   cameraContainer.classList.remove('max-h-[600px]', 'opacity-100', 'scale-100');
   cameraContainer.classList.add('max-h-0', 'opacity-0', 'scale-95', 'pointer-events-none');
   setTimeout(() => {
       if (isCameraHidden) {
           standbyContainer.classList.remove('hidden');
       }
   }, 500);
                    }
                }
            }
        }

        setInterval(fetchStatus, 1000);

        function openModal() {
            document.getElementById('cancel-confirm-box').classList.add('hidden');
            document.getElementById('reg-modal').classList.remove('hidden');
        }
        
        function closeModal() { 
            const form = document.getElementById('reg-form');
            const hasData = Array.from(form.elements).some(input => 
                (input.type === 'text' || input.type === 'number') && input.value.trim() !== ''
            );
            
            if (hasData) {
                document.getElementById('cancel-confirm-box').classList.remove('hidden');
            } else {
                document.getElementById('reg-modal').classList.add('hidden');
                form.reset();
                handleUserTypeChange('Student');
            }
        }

        function dismissConfirmClose(confirmCancel) {
            document.getElementById('cancel-confirm-box').classList.add('hidden');
            if (confirmCancel) {
                document.getElementById('reg-modal').classList.add('hidden');
                document.getElementById('reg-form').reset();
                handleUserTypeChange('Student');
            }
        }

        // AJAX Form Submission (No page reload, no browser alerts)
        function submitRegistration(event) {
            event.preventDefault();
            const form = document.getElementById('reg-form');
            const formData = new FormData(form);
            const btn = document.getElementById('submit-btn');
            const originalBtnHtml = btn.innerHTML;
            
            btn.innerHTML = `<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Saving & Training Face...`;
            btn.disabled = true;

            fetch('/register', { 
                method: 'POST', 
                body: formData 
            })
            .then(res => res.json().then(data => ({ status: res.status, data })))
            .then(({ status, data }) => {
                if (status >= 200 && status < 300 && data.success !== false) {
                    showToast(data.message || 'Registration successful! Face trained.', 'success');
                    document.getElementById('reg-modal').classList.add('hidden');
                    form.reset();
                    handleUserTypeChange('Student');
                } else {
                    showToast(data.message || 'Registration failed. Please check the required fields.', 'error');
                }
                btn.innerHTML = originalBtnHtml;
                btn.disabled = false;
            })
            .catch(() => {
                showToast('An unexpected network error occurred. Please try again.', 'error');
                btn.innerHTML = originalBtnHtml;
                btn.disabled = false;
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return redirect(url_for('login_page'))

# ==================== New Login and Guard Routes ====================

# Login page HTML template with two large buttons
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GuardGate Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        html, body {height: 100%; width: 100%; margin: 0; overflow: hidden;}
        body {font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%);}
        .app-root {height: 100vh; height: 100dvh; width: 100vw; overflow: hidden;}
    </style>
</head>
<body class="text-slate-800 antialiased overflow-hidden">
    <div class="app-root flex items-center justify-center p-4">
        <div class="w-full max-w-sm max-h-full overflow-y-auto bg-white rounded-2xl shadow-lg shadow-emerald-900/5 border border-emerald-900/10 p-6 sm:p-8 text-center">
            <div class="mx-auto w-12 h-12 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md shadow-emerald-800/15 mb-4">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
            </div>
            <h1 class="text-2xl font-bold text-emerald-950 tracking-tight">GuardGate</h1>
            <p class="text-xs text-emerald-900/60 font-medium mt-1 mb-6">Select how you want to continue</p>
            <div class="flex flex-col gap-3">
                <a href="{{ url_for('scanner') }}" class="block bg-emerald-800 hover:bg-emerald-900 text-white text-sm font-semibold py-3 px-6 rounded-xl shadow-sm transition-colors">Student</a>
                <a href="{{ url_for('guard_login') }}" class="block bg-white hover:bg-emerald-50 text-emerald-900 text-sm font-semibold py-3 px-6 rounded-xl border border-emerald-200 shadow-sm transition-colors">Guard</a>
            </div>
        </div>
    </div>
</body>
</html>"""

# Scanner route (previous home page)
@app.route('/scanner')
def scanner():
    return render_template_string(HTML_TEMPLATE)

# Login page route
@app.route('/login')
def login_page():
    return render_template_string(LOGIN_TEMPLATE)

# Guard login form template
GUARD_LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guard Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        html, body {height: 100%; width: 100%; margin: 0; overflow: hidden;}
        body {font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%);}
        .app-root {height: 100vh; height: 100dvh; width: 100vw; overflow: hidden;}
    </style>
</head>
<body class="text-slate-800 antialiased overflow-hidden">
    <div class="app-root flex items-center justify-center p-4">
        <div class="w-full max-w-sm max-h-full overflow-y-auto bg-white rounded-2xl shadow-lg shadow-emerald-900/5 border border-emerald-900/10 p-6 sm:p-8">
            <h2 class="text-2xl font-bold text-emerald-950 tracking-tight">Guard Login</h2>
            <p class="text-xs text-emerald-900/60 font-medium mt-1 mb-6">Sign in to open the admin station</p>
            {% if error %}<p class="mb-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium px-3 py-2">{{ error }}</p>{% endif %}
            <form method="POST" action="{{ url_for('guard_login') }}" class="space-y-4">
                <div>
                    <label for="username" class="block text-xs font-semibold text-slate-700 mb-1.5">Username</label>
                    <input id="username" type="text" name="username" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm shadow-sm outline-none transition focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600"/>
                </div>
                <div>
                    <label for="password" class="block text-xs font-semibold text-slate-700 mb-1.5">Password</label>
                    <input id="password" type="password" name="password" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm shadow-sm outline-none transition focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600"/>
                </div>
                <button type="submit" class="w-full bg-emerald-800 hover:bg-emerald-900 text-white text-sm font-semibold py-2.5 rounded-xl shadow-sm transition-colors">Login</button>
            </form>
        </div>
    </div>
</body>
</html>"""

# Guard login handling
@app.route('/guard_login', methods=['GET', 'POST'])
def guard_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'mmsu@guard123' and password == 'mmsuGuard':
            session['is_guard'] = True
            return redirect(url_for('guard_bp.guard_page'))
        else:
            return render_template_string(GUARD_LOGIN_TEMPLATE, error='Invalid credentials')
    return render_template_string(GUARD_LOGIN_TEMPLATE)

# Logout route
@app.route('/logout')
def logout():
    session.pop('is_guard', None)
    return redirect(url_for('login_page'))

# ==================== End New Routes ====================

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify(system_status)

@app.route('/register', methods=['POST'])
def register():
    global current_unrecognized_frame
    try:
        user_type = request.form.get('user_type', 'Student').strip()
        surname = request.form.get('surname', '').strip()
        fname = request.form.get('fname', '').strip()
        mname = request.form.get('mname', '').strip()
        suffix = request.form.get('suffix', 'N/A').strip() or 'N/A'

        if not surname or not fname:
            return jsonify({"success": False, "message": "Surname and First Name are required!"}), 400

        short_id = uuid.uuid4().hex[:6].upper()

        if user_type == 'Parent':
            address = request.form.get('parent_address', '').strip()
            if not mname:
                return jsonify({"success": False, "message": "Middle Name is required for Parents!"}), 400
            if not address:
                return jsonify({"success": False, "message": "Address is required for Parents!"}), 400
            
            student_id = f"PAR-{short_id}"
            college = "Parent"
            course = address

        elif user_type == 'Faculty':
            faculty_college = request.form.get('faculty_college', '').strip()
            department = request.form.get('department', '').strip()
            if not faculty_college:
                return jsonify({"success": False, "message": "College is required for Faculty!"}), 400
            if not department:
                return jsonify({"success": False, "message": "Department is required for Faculty!"}), 400
            
            student_id = f"FAC-{short_id}"
            college = "Faculty"
            # Category stays "Faculty" so Guard filters keep working; the faculty's college is stored with the department
            course = f"{faculty_college} - {department}"

        elif user_type == 'Others':
            address = request.form.get('other_address', '').strip() or "Visitor"
            student_id = f"OTH-{short_id}"
            college = "Others"
            course = address

        else:  # Student
            student_id = request.form.get('student_id', '').strip()
            college = request.form.get('college', '').strip()
            course = request.form.get('course', '').strip()

            if not student_id or not college or not course:
                return jsonify({"success": False, "message": "Student ID, College, and Course & Year are required!"}), 400

        if current_unrecognized_frame is None:
            return jsonify({"success": False, "message": "No face frame captured. Please position yourself in front of the camera."}), 400

        normalized_name = f"{surname}, {fname}, {mname or 'N/A'}, {suffix}"
        
        success, encoded_img = cv2.imencode('.jpg', current_unrecognized_frame)
        if not success:
            return jsonify({"success": False, "message": "Failed to process image frame."}), 500
        
        img_bytes = encoded_img.tobytes()
        file_path_storage = f"{student_id}.jpg"

        supabase.storage.from_("faces").upload(
            path=file_path_storage, 
            file=img_bytes, 
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )

        public_url = supabase.storage.from_("faces").get_public_url(file_path_storage)

        supabase.table("visitors").insert({
            "student_id": student_id,
            "normalized_name": normalized_name,
            "college": college,
            "course_year": course,
            "image_path": public_url
        }).execute()

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        supabase.table("logs").insert({
            "student_id": student_id,
            "normalized_name": normalized_name,
            "college": college,
            "course_year": course,
            "action": "Time In",
            "timestamp": timestamp
        }).execute()

        load_recognizer_training()
        return jsonify({
            "success": True, 
            "message": f"Successfully registered and timed in {normalized_name} ({user_type})!"
        })
    except Exception as e:
        logging.error(f"Registration save error: {e}")
        return jsonify({"success": False, "message": f"Failed to register visitor: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)