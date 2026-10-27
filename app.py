import os
import time
import logging
import uuid
import threading
import hashlib
import cv2
import numpy as np
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
from supabase import create_client, Client
from supabase_auth import datetime
from datetime import datetime, timezone, timedelta
from admin import admin_bp
from guard import guard_bp

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = 'super-secret-key-please-change'
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

# I-register ang guard_bp para ma-call ang guard.py sa port 5000
app.register_blueprint(guard_bp)
app.register_blueprint(admin_bp)

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
cv_lock = threading.Lock()
model_signature = None
last_sync_check = 0.0
SYNC_INTERVAL = 5
sync_lock = threading.Lock()

# Timer delay configuration (2.5 seconds hold before triggering Time In/Out)
VERIFICATION_DELAY = 2.5
COOLDOWN_SECONDS = 3
ATTENDANCE_GRACE = 2.0
FACE_LOST_RESET = 1.5

# Recognition tuning. LBPH returns a distance: LOWER = better match.
# The old value (100) accepted almost any face, so the first registered visitor "won" for everyone.
MATCH_THRESHOLD = 42       # a face is only accepted if its best distance is BELOW this (typical true match: 30-50)
MATCH_MARGIN = 10          # with 2+ people enrolled, the runner-up must be at least this much farther away
DEBUG_CONFIDENCE = True   # set True to print each prediction's distance while tuning MATCH_THRESHOLD
FACE_SIZE = 200
MIN_FACE_RATIO = 0.15      # smallest accepted face, as a fraction of frame width
MAX_FACES_PER_FRAME = 1    # evaluate up to this many faces per frame (largest first)
CLIENT_TTL = 600
DEFAULT_STATUS_TEXT = "System Active: Scanning for registered visitors..."
PRESENCE_TTL = 15
PH_TZ = timezone(timedelta(hours=8))

client_states = {}
client_states_lock = threading.Lock()

def new_client_state():
    return {
        "cooldown_timer": 0,
        "cooldowns": {},
        "verifying": {},          # visitor_id -> time their hold-still timer started
        "last_face_seen_time": 0,
        "last_active": time.time(),
        "current": {"visitor": None, "verified": False, "seen": 0},
        "presence": {"id": None, "data": None, "fetched": 0},
        "system_status": {
            "text": DEFAULT_STATUS_TEXT,
            "status": "normal",
            "unknown_detected": False,
            "face_detected": False
        }
    }

def get_client_state(client_id):
    now = time.time()
    with client_states_lock:
        stale = [k for k, v in client_states.items() if now - v["last_active"] > CLIENT_TTL]
        for key in stale:
            del client_states[key]
        state = client_states.get(client_id)
        if state is None:
            state = new_client_state()
            client_states[client_id] = state
        state["last_active"] = now
        return state

script_dir = os.path.dirname(os.path.abspath(__file__))
cascade_path = os.path.join(script_dir, 'haarcascade_frontalface_default.xml')
if not os.path.exists(cascade_path):
    cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
face_cascade = cv2.CascadeClassifier(cascade_path)


# --- app.py (Line 104) ---

def detect_faces(gray, relaxed=False):
    """Detect faces on a grayscale frame. Returns boxes sorted largest first."""
    frame_w = gray.shape[1]
    min_side = max(30 if relaxed else 48, int(frame_w * (0.04 if relaxed else MIN_FACE_RATIO)))
    equalized = cv2.equalizeHist(gray)
    with cv_lock:
        faces = face_cascade.detectMultiScale(
            equalized,
            scaleFactor=1.05 if relaxed else 1.08,
            minNeighbors=4 if relaxed else 8,  # Increased from 6 to 8 for tighter filtering
            minSize=(min_side, min_side),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
    boxes = [tuple(int(v) for v in f) for f in faces]
    boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
    return boxes


def face_from_gray(gray, box):
    x, y, w, h = box

    # Relaxed trimming so distinct features aren't lost
    trim_x = int(w * 0.12)      # Was 0.18
    trim_y_top = int(h * 0.15)  # Was 0.22
    trim_y_bot = int(h * 0.10)
    
    roi = gray[max(0, y + trim_y_top):y + h - trim_y_bot, max(0, x + trim_x):x + w - trim_x]
    if roi.size == 0:
        roi = gray[y:y + h, x:x + w]
        
    roi = cv2.resize(roi, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA)
    # Stronger CLAHE grid to flatten harsh room lighting differences
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(roi)


def augment_face(face):
    """Generates robust variations (flips, shifts, lighting) to fix 1-shot learning weakness."""
    samples = [face]
    h, w = face.shape
    
    # Brightness variations
    samples.append(cv2.convertScaleAbs(face, alpha=1.05, beta=10))
    samples.append(cv2.convertScaleAbs(face, alpha=0.95, beta=-10))
    
    # Spatial Jitter (accounts for bounding box bouncing in live video)
    for dx in (-6, 6):
        for dy in (-6, 6):
            m = np.float32([[1, 0, dx], [0, 1, dy]])
            samples.append(cv2.warpAffine(face, m, (w, h), borderMode=cv2.BORDER_REPLICATE))
    
    # Mirror images for symmetrical posing
    flipped = cv2.flip(face, 1)
    samples.append(flipped)
    for dx in (-4, 4):
        m = np.float32([[1, 0, dx], [0, 1, 0]])
        samples.append(cv2.warpAffine(flipped, m, (w, h), borderMode=cv2.BORDER_REPLICATE))
        
    return samples


def extract_training_face(gray, label):
    """Registration stores the whole camera frame, so find and crop the face before training."""
    boxes = detect_faces(gray) or detect_faces(gray, relaxed=True)
    if boxes:
        return face_from_gray(gray, boxes[0])
    logging.error(f"No face found in stored image for {label}; using centre crop.")
    h, w = gray.shape[:2]
    side = min(h, w)
    return face_from_gray(gray, ((w - side) // 2, (h - side) // 2, side, side))


def signature_of(rows):
    parts = sorted(
        f"{r.get('student_id')}|{r.get('normalized_name')}|{r.get('college')}|{r.get('course_year')}"
        for r in rows
    )
    return hashlib.md5("\n".join(parts).encode("utf-8")).hexdigest()


def fetch_all_visitor_rows(columns="*"):
    rows = []
    offset = 0
    page = 1000
    while True:
        batch = supabase.table("visitors").select(columns).order("student_id").range(offset, offset + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def prune_local_faces(keep):
    try:
        for name in os.listdir(FACE_DIR):
            if name.endswith(".jpg") and name not in keep:
                os.remove(os.path.join(FACE_DIR, name))
    except Exception as ex:
        logging.error(f"Failed to prune local face cache: {ex}")


def load_recognizer_training():
    global visitor_map, is_trained, recognizer, model_signature
    new_map = {}
    faces_train = []
    ids_train = []
    current_id = 0
    complete = True

    try:
        raw_visitors = fetch_all_visitor_rows()
        new_signature = signature_of(raw_visitors)

        if not raw_visitors:
            prune_local_faces(set())
            with cv_lock:
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                visitor_map = {}
                is_trained = False
                model_signature = new_signature
            return

        unique_visitors = {}
        for row in raw_visitors:
            unique_visitors[row["student_id"]] = row

        visitors = list(unique_visitors.values())
        prune_local_faces({f"{v['student_id']}.jpg" for v in visitors})

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
                    complete = False
                    continue

            img = cv2.imread(local_img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                complete = False
                continue

            for sample in augment_face(extract_training_face(img, s_id)):
                faces_train.append(sample)
                ids_train.append(current_id)
            new_map[current_id] = {
                "Student_ID": s_id,
                "Name": row["normalized_name"],
                "College": row["college"],
                "Course": row["course_year"]
            }
            current_id += 1

        new_recognizer = None
        if faces_train:
            new_recognizer = cv2.face.LBPHFaceRecognizer_create(grid_x=8, grid_y=8)
            new_recognizer.train(faces_train, np.array(ids_train))

        with cv_lock:
            if new_recognizer is not None:
                recognizer = new_recognizer
                visitor_map = new_map
                is_trained = True
            else:
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                visitor_map = {}
                is_trained = False
            if complete:
                model_signature = new_signature
    except Exception as e:
        logging.error(f"Error loading training data from Supabase: {e}")


def ensure_recognizer_fresh():
    global last_sync_check
    now = time.time()
    if now - last_sync_check < SYNC_INTERVAL:
        return
    if not sync_lock.acquire(blocking=False):
        return
    try:
        last_sync_check = now
        try:
            current = signature_of(fetch_all_visitor_rows("student_id,normalized_name,college,course_year"))
        except Exception as ex:
            logging.error(f"Failed to check visitor list: {ex}")
            return
        if current != model_signature:
            load_recognizer_training()
    finally:
        sync_lock.release()


load_recognizer_training()


def identify_face(face_roi):
    """Return (visitor or None, best_distance). Call while holding cv_lock."""
    ranked = None
    try:
        collector = cv2.face.StandardCollector_create()
        recognizer.predict_collect(face_roi, collector)
        best = {}
        for label, dist in collector.getResults(True):
            label = int(label)
            dist = float(dist)
            if label not in best or dist < best[label]:
                best[label] = dist
        ranked = sorted(best.items(), key=lambda kv: kv[1])
    except Exception:
        ranked = None

    if not ranked:
        try:
            label, dist = recognizer.predict(face_roi)
            ranked = [(int(label), float(dist))]
        except Exception:
            return None, 999.0

    label, dist = ranked[0]

    if DEBUG_CONFIDENCE:
        runner_up = f"{ranked[1][1]:.1f}" if len(ranked) > 1 else "-"
        print(f"[recognizer] label={label} best={dist:.1f} runner_up={runner_up}")

    if dist >= MATCH_THRESHOLD:
        return None, dist

    if len(ranked) > 1 and ranked[1][1] - dist < MATCH_MARGIN:
        return None, dist

    return visitor_map.get(label), dist


def parse_log_timestamp(value):
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def get_presence(s_id):
    presence = {"inside": False, "stale": False, "last_action": None, "last_timestamp": None}
    res = supabase.table("logs").select("action, timestamp") \
        .eq("student_id", s_id).order("id", desc=True).limit(1).execute()
    if not res.data:
        return presence

    last = res.data[0]
    presence["last_action"] = last["action"]
    presence["last_timestamp"] = last["timestamp"]
    if last["action"] == "Time In":
        last_dt = parse_log_timestamp(last["timestamp"])
        today = datetime.now(PH_TZ).strftime("%Y-%m-%d")
        if last_dt and last_dt.strftime("%Y-%m-%d") != today:
            presence["stale"] = True
        else:
            presence["inside"] = True
    return presence


def cached_presence(state, s_id):
    cache = state["presence"]
    now = time.time()
    if cache["id"] != s_id or cache["data"] is None or now - cache["fetched"] > PRESENCE_TTL:
        try:
            cache["data"] = get_presence(s_id)
        except Exception as e:
            logging.error(f"Error reading presence for {s_id}: {e}")
            cache["data"] = {"inside": False, "stale": False, "last_action": None, "last_timestamp": None}
        cache["id"] = s_id
        cache["fetched"] = now
    return cache["data"]


def pretty_name(raw):
    parts = [p.strip() for p in (raw or "").split(",")]
    parts = [p for p in parts if p and p.upper() != "N/A"]
    if len(parts) <= 1:
        return parts[0] if parts else (raw or "-")
    return f"{parts[0]}, {' '.join(parts[1:])}"


def name_initials(raw):
    parts = [p.strip() for p in (raw or "").split(",")]
    surname = parts[0] if parts else ""
    first = parts[1] if len(parts) > 1 else ""
    return ((first[:1] + surname[:1]) or "?").upper()


def describe_visitor(visitor):
    college = visitor["College"]
    course = visitor["Course"] or "-"
    if college == "Parent":
        return "Parent", "-", "Home Address", course
    if college == "Faculty":
        faculty_college, _, department = course.partition(" - ")
        if department:
            return "Faculty", faculty_college, "Department", department
        return "Faculty", "-", "Department", course
    if college == "Others":
        return "Others", "-", "Address or Purpose of Visit", course
    return "Student", college, "Course and Year", course


def record_attendance(visitor, action):
    s_id = visitor["Student_ID"]
    name = visitor["Name"]
    college = visitor["College"]
    course = visitor["Course"]
    shown = pretty_name(name)

    presence = get_presence(s_id)
    if action == "Time In" and presence["inside"]:
        return False, f"{shown} is already timed in."
    if action == "Time Out" and not presence["inside"]:
        return False, f"{shown} is not timed in yet."

    if presence["stale"]:
        previous = parse_log_timestamp(presence["last_timestamp"])
        if previous:
            supabase.table("logs").insert({
                "student_id": s_id,
                "normalized_name": name,
                "college": college,
                "course_year": course,
                "action": "Time Out",
                "timestamp": f"{previous.strftime('%Y-%m-%d')} 11:59:59 PM"
            }).execute()

    timestamp = datetime.now(PH_TZ).strftime("%Y-%m-%d %I:%M:%S %p")
    supabase.table("logs").insert({
        "student_id": s_id,
        "normalized_name": name,
        "college": college,
        "course_year": course,
        "action": action,
        "timestamp": timestamp
    }).execute()
    return True, f"{action} recorded for {shown}."


def reset_verification(state):
    state["verifying"] = {}
    state["current"] = {"visitor": None, "verified": False, "seen": 0}


def current_payload(state, now):
    current = state["current"]
    visitor = current["visitor"]
    if visitor is None or now - current["seen"] > FACE_LOST_RESET:
        return None

    s_id = visitor["Student_ID"]
    presence = cached_presence(state, s_id)
    cooling = now < state["cooldowns"].get(s_id, 0)
    ready = current["verified"] and not cooling
    category, college, detail_label, detail = describe_visitor(visitor)

    return {
        "id": s_id,
        "name": pretty_name(visitor["Name"]),
        "initials": name_initials(visitor["Name"]),
        "category": category,
        "college": college,
        "detail_label": detail_label,
        "detail": detail,
        "inside": presence["inside"],
        "last_action": presence["last_action"],
        "last_timestamp": presence["last_timestamp"],
        "verified": current["verified"],
        "cooling": cooling,
        "can_time_in": ready and not presence["inside"],
        "can_time_out": ready and presence["inside"]
    }


def analyze_frame(frame, state):
    system_status = state["system_status"]
    frame_h, frame_w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = detect_faces(gray)[:MAX_FACES_PER_FRAME]

    current_time = time.time()
    has_face = len(faces) > 0
    system_status["face_detected"] = has_face

    if not has_face:
        if current_time - state["last_face_seen_time"] > FACE_LOST_RESET:
            reset_verification(state)

        if not system_status["unknown_detected"] and current_time > state["cooldown_timer"] + 2:
            system_status["text"] = DEFAULT_STATUS_TEXT
            system_status["status"] = "normal"
            system_status["unknown_detected"] = False

        result = dict(system_status)
        result["box"] = None
        result["boxes"] = []
        result["visitor"] = current_payload(state, current_time)
        return result

    state["last_face_seen_time"] = current_time

    identities = [None] * len(faces)
    if is_trained:
        claims = []
        with cv_lock:
            for i, box_xywh in enumerate(faces):
                visitor, distance = identify_face(face_from_gray(gray, box_xywh))
                if visitor is not None:
                    claims.append((distance, i, visitor))

        claims.sort(key=lambda c: c[0])
        taken = set()
        for distance, i, visitor in claims:
            if visitor["Student_ID"] in taken:
                continue
            taken.add(visitor["Student_ID"])
            identities[i] = visitor

    verifying = state["verifying"]
    seen_ids = set()
    boxes = []
    unknown_count = 0
    verifying_best = None
    focus = None

    for i, (x, y, w, h) in enumerate(faces):
        box = {
            "x": x / frame_w,
            "y": y / frame_h,
            "w": w / frame_w,
            "h": h / frame_h,
            "color": "amber",
            "label": "",
            "progress": None
        }
        visitor = identities[i]

        if visitor is None:
            if is_trained:
                box["color"] = "red"
                box["label"] = "Unknown"
                unknown_count += 1
        else:
            visitor_id = visitor["Student_ID"]
            visitor_first_name = visitor["Name"].split(",")[0]
            seen_ids.add(visitor_id)
            box["color"] = "green"
            cooling = current_time < state["cooldowns"].get(visitor_id, 0)
            verified = False

            if cooling:
                verifying.pop(visitor_id, None)
                box["label"] = f"{visitor_first_name} (Recorded)"
            else:
                start = verifying.setdefault(visitor_id, current_time)
                elapsed = current_time - start
                remaining = max(0.0, VERIFICATION_DELAY - elapsed)
                verified = elapsed >= VERIFICATION_DELAY

                if verified:
                    box["label"] = f"{visitor_first_name} (Verified)"
                else:
                    box["progress"] = min(1.0, elapsed / VERIFICATION_DELAY)
                    box["label"] = f"{visitor_first_name}: {remaining:.1f}s"
                    if verifying_best is None or remaining < verifying_best[0]:
                        verifying_best = (remaining, visitor)

            if focus is None:
                focus = (visitor, verified, cooling)

        boxes.append(box)

    for stale_id in [k for k in verifying if k not in seen_ids]:
        verifying.pop(stale_id, None)

    if focus is not None:
        state["current"] = {"visitor": focus[0], "verified": focus[1], "seen": current_time}
    else:
        state["current"] = {"visitor": None, "verified": False, "seen": 0}

    system_status["unknown_detected"] = (unknown_count > 0) or (not is_trained)
    if not is_trained:
        system_status["text"] = "Please register your face."
        system_status["status"] = "warning"
    elif focus is not None and focus[1]:
        system_status["text"] = f"Verified: {pretty_name(focus[0]['Name'])}. Choose Time In or Time Out."
        system_status["status"] = "success"
    elif focus is not None and focus[2]:
        if system_status["status"] != "success":
            system_status["text"] = f"Recorded: {pretty_name(focus[0]['Name'])}."
            system_status["status"] = "success"
    elif verifying_best is not None:
        remaining, visitor = verifying_best
        system_status["text"] = f"Face Detected: {pretty_name(visitor['Name'])} : Hold still ({remaining:.1f}s)..."
        system_status["status"] = "verifying"
    elif unknown_count > 0:
        system_status["text"] = "Unknown Face Detected : Please Register"
        system_status["status"] = "error"

    result = dict(system_status)
    result["boxes"] = boxes
    result["box"] = boxes[0] if boxes else None
    result["visitor"] = current_payload(state, current_time)
    return result

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
        <main class="flex-1 min-h-0 p-3 sm:p-5">
            <div class="h-full w-full max-w-6xl mx-auto flex flex-col md:flex-row bg-white rounded-2xl shadow-lg shadow-emerald-900/5 border border-emerald-900/10 overflow-hidden">

                <!-- LEFT: INFORMATION AND CREDENTIALS -->
                <section class="order-2 md:order-1 flex-1 min-w-0 min-h-0 flex flex-col">
                    <div class="shrink-0 px-4 sm:px-5 py-3 border-b border-emerald-900/5 bg-emerald-50/40 flex justify-between items-center gap-2">
                        <span class="text-xs font-semibold uppercase tracking-wider text-emerald-900 flex items-center gap-2 min-w-0">
                            <svg class="w-4 h-4 text-emerald-700 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2"></path></svg>
                            <span class="truncate">Visitor Credentials</span>
                        </span>
                        <span class="shrink-0 text-[11px] font-medium text-emerald-800 bg-emerald-100/70 px-2.5 py-0.5 rounded-full">
                            Verify: 2.5s Hold
                        </span>
                    </div>

                    <div class="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5 space-y-4">
                        <div id="status-panel" class="rounded-xl border border-emerald-900/10 bg-emerald-50/50 px-4 py-3 text-center text-sm font-medium text-emerald-800 transition-colors duration-300">
                            System Active: Scanning for registered visitors...
                        </div>

                        <div class="rounded-xl border border-emerald-900/10 overflow-hidden">
                            <div class="flex items-center gap-4 p-4 bg-emerald-50/50 border-b border-emerald-900/10">
                                <div id="v-avatar" class="w-14 h-14 shrink-0 rounded-2xl bg-slate-300 text-white flex items-center justify-center text-lg font-bold">--</div>
                                <div class="min-w-0 flex-1">
                                    <p id="v-name" class="text-base sm:text-lg font-bold text-emerald-950 truncate">No visitor detected</p>
                                    <p id="v-id" class="text-xs font-medium text-emerald-900/60 truncate">Step in front of the camera</p>
                                </div>
                                <span id="v-presence" class="hidden shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-full border"></span>
                            </div>
                            <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 p-4">
                                <div>
                                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Category</dt>
                                    <dd id="v-category" class="mt-0.5 text-sm font-semibold text-slate-800">-</dd>
                                </div>
                                <div>
                                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">College</dt>
                                    <dd id="v-college" class="mt-0.5 text-sm font-semibold text-slate-800">-</dd>
                                </div>
                                <div class="sm:col-span-2">
                                    <dt id="v-detail-label" class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Course / Dept / Address</dt>
                                    <dd id="v-detail" class="mt-0.5 text-sm font-semibold text-slate-800 break-words">-</dd>
                                </div>
                                <div>
                                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Last Action</dt>
                                    <dd id="v-last-action" class="mt-0.5 text-sm font-semibold text-slate-800">-</dd>
                                </div>
                                <div>
                                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recorded At</dt>
                                    <dd id="v-last-time" class="mt-0.5 text-sm font-semibold text-slate-800">-</dd>
                                </div>
                            </dl>
                        </div>
                    </div>

                    <div class="shrink-0 p-4 sm:p-5 border-t border-emerald-900/10 bg-white">
                        <div class="grid grid-cols-2 gap-3">
                            <button id="time-in-btn" type="button" onclick="recordAttendance('Time In')" disabled class="py-3 px-4 text-sm font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition shadow-sm disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-emerald-700">
                                Time In
                            </button>
                            <button id="time-out-btn" type="button" onclick="recordAttendance('Time Out')" disabled class="py-3 px-4 text-sm font-semibold text-rose-700 bg-white border border-rose-200 rounded-xl hover:bg-rose-50 focus:ring-4 focus:ring-rose-500/20 transition shadow-sm disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white">
                                Time Out
                            </button>
                        </div>
                        <button id="register-btn" type="button" onclick="openModal()" class="hidden mt-3 w-full py-2.5 px-4 text-sm font-semibold text-emerald-800 bg-white border border-emerald-200 rounded-xl hover:bg-emerald-50 transition shadow-sm flex items-center justify-center gap-2">
                            <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
                            Register New Visitor
                        </button>
                    </div>
                </section>

                <!-- RIGHT: SMALL CAMERA FEED -->
                <aside class="order-1 md:order-2 shrink-0 w-full md:w-80 lg:w-96 border-b md:border-b-0 md:border-l border-emerald-900/10 bg-slate-50/60 p-3 md:p-4 flex flex-col min-h-0">
                    <div class="mb-2 md:mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-900">
                        <svg class="w-4 h-4 text-emerald-700 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        Live Camera
                    </div>

                    <div id="camera-container" class="relative bg-slate-900 w-full max-w-[14rem] md:max-w-none mx-auto aspect-video rounded-xl overflow-hidden shadow-sm">
                        <video id="webcam" autoplay playsinline muted class="object-contain h-full w-full opacity-95 -scale-x-100"></video>
                        <canvas id="overlay" class="absolute inset-0 h-full w-full pointer-events-none"></canvas>

                        <div id="standby-container" class="hidden absolute inset-0 p-3 text-center bg-slate-900 text-slate-400 flex flex-col items-center justify-center gap-2">
                            <svg class="w-6 h-6 text-emerald-400 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                            <p class="text-xs font-semibold text-slate-200">Scanner on Standby</p>
                            <p class="text-[11px] text-slate-400">Step in front of the camera to wake it up.</p>
                        </div>
                    </div>

                    <ol class="hidden md:block mt-4 space-y-2 text-xs text-slate-600 leading-relaxed overflow-y-auto min-h-0">
                        <li class="flex gap-2.5"><span class="shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold flex items-center justify-center">1</span>Face the camera and hold still until you are verified.</li>
                        <li class="flex gap-2.5"><span class="shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold flex items-center justify-center">2</span>Check your credentials on the left.</li>
                        <li class="flex gap-2.5"><span class="shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold flex items-center justify-center">3</span>Press Time In to enter or Time Out to leave.</li>
                        <li class="flex gap-2.5"><span class="shrink-0 w-5 h-5 rounded-full bg-slate-200 text-slate-600 text-[11px] font-bold flex items-center justify-center">?</span>Not recognized? Use Register New Visitor.</li>
                    </ol>
                </aside>
            </div>
        </main>
    </div>

    <!-- REGISTRATION MODAL -->
    <div id="reg-modal" class="hidden fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 transition-opacity duration-300 overflow-hidden">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[94vh] max-h-[94dvh] flex flex-col overflow-hidden border border-emerald-900/15 relative">
            
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
                <div class="grid grid-cols-1 md:grid-cols-5 gap-6">
                <div class="md:col-span-3 min-w-0">
                
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
   <input type="text" name="surname" id="field_surname" required placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">First Name <span class="text-rose-600">*</span></label>
   <input type="text" name="fname" id="field_fname" required placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label id="label_mname" class="block text-xs font-semibold text-slate-700">Middle Name <span class="text-slate-400 font-normal">(Optional)</span></label>
   <input type="text" name="mname" id="field_mname" placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
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

                <!-- STUDENT SECTION: COLLEGE DROPDOWN, STUDENT ID, YEAR LEVEL (1-4), COURSE / PROGRAM -->
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
   <input type="text" name="student_id" id="field_student_id" required placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Year Level <span class="text-rose-600">*</span></label>
   <select name="year_level" id="field_year" required class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm bg-white cursor-pointer">
       <option value="" disabled selected>Select Year...</option>
       <option value="1">1</option>
       <option value="2">2</option>
       <option value="3">3</option>
       <option value="4">4</option>
   </select>
                    </div>
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">Course / Program <span class="text-rose-600">*</span></label>
   <input type="text" name="course" id="field_course" required maxlength="40" placeholder="e.g. BSCS" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm uppercase placeholder:normal-case focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- PARENT SECTION: same grid as Student, no ID and no college (suffix is in the shared name fields) -->
                <div id="group-parent" class="hidden mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-1.5 md:col-span-2">
   <label class="block text-xs font-semibold text-slate-700">Home / Residential Address <span class="text-rose-600">*</span></label>
   <input type="text" name="parent_address" id="field_parent_address" placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
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
   <label class="block text-xs font-semibold text-slate-700">Department<span class="text-rose-600">*</span></label>
   <input type="text" name="department" id="field_department" placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                <!-- OTHERS SECTION: NAME FIELDS + ADDRESS/PURPOSE -->
                <div id="group-others" class="hidden mt-4 pt-4 border-t border-slate-100">
                    <div class="space-y-1.5">
   <label class="block text-xs font-semibold text-slate-700">Address or Purpose of Visit <span class="text-rose-600">*</span></label>
   <input type="text" name="other_address" id="field_other_address" placeholder="" class="w-full border border-slate-300 rounded-lg px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 transition shadow-sm">
                    </div>
                </div>

                </div>

                <!-- FACE CAPTURE -->
                <div class="md:col-span-2 min-w-0">
                    <div class="md:sticky md:top-0 rounded-xl border border-emerald-200/80 bg-emerald-50/40 p-4">
                        <label class="block text-xs font-bold uppercase tracking-wider text-emerald-900 mb-2">
                            Face Capture <span class="text-rose-600">*</span>
                        </label>
                        <div class="relative w-full aspect-video rounded-lg overflow-hidden bg-slate-900">
                            <video id="reg-video" autoplay playsinline muted class="absolute inset-0 h-full w-full object-contain -scale-x-100"></video>
                            <img id="reg-preview" alt="Captured face" class="hidden absolute inset-0 h-full w-full object-contain bg-slate-900">
                        </div>
                        <p id="capture-hint" class="mt-2 text-[11px] font-medium text-emerald-800/80">Face the camera in good light, then press Capture Photo.</p>
                        <div class="mt-3 grid grid-cols-1 gap-2">
                            <button type="button" id="capture-btn" onclick="captureFace()" class="w-full px-4 py-2.5 text-sm font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition shadow-sm disabled:opacity-60 disabled:cursor-not-allowed">
                                Capture Photo
                            </button>
                            <button type="button" id="retake-btn" onclick="retakeFace()" class="hidden w-full px-4 py-2.5 text-sm font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">
                                Retake
                            </button>
                        </div>
                    </div>
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
                    <button id="submit-btn" type="submit" disabled class="px-5 py-2.5 text-sm font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition-all shadow-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-emerald-700">
   <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
   Save
                    </button>
                </div>
            </form>
        </div>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        let lastFaceTime = Date.now();
        let isCameraHidden = false;
        let actionBusy = false;
        let capturedBlob = null;
        let capturedUrl = null;

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
                <div data-msg class="flex-1 text-xs leading-relaxed break-words"></div>
                <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-slate-600 p-0.5 rounded-lg transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            `;
            toast.querySelector('[data-msg]').textContent = message;

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
            document.getElementById('field_year').required = false;
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
                document.getElementById('field_year').required = true;
                hintText.innerText = 'Student registration requiring Student ID, College, Year Level, and Course.';
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

        function setText(id, value) {
            document.getElementById(id).innerText = value;
        }

        function renderVisitor(v) {
            const avatar = document.getElementById('v-avatar');
            const presence = document.getElementById('v-presence');
            const inBtn = document.getElementById('time-in-btn');
            const outBtn = document.getElementById('time-out-btn');
            const avatarBase = 'w-14 h-14 shrink-0 rounded-2xl text-white flex items-center justify-center text-lg font-bold ';

            if (!v) {
                setText('v-avatar', '--');
                avatar.className = avatarBase + 'bg-slate-300';
                setText('v-name', 'No visitor detected');
                setText('v-id', 'Step in front of the camera');
                presence.classList.add('hidden');
                ['v-category', 'v-college', 'v-detail', 'v-last-action', 'v-last-time'].forEach(id => setText(id, '-'));
                setText('v-detail-label', 'Course / Dept / Address');
                inBtn.disabled = true;
                outBtn.disabled = true;
                return;
            }

            setText('v-avatar', v.initials);
            avatar.className = avatarBase + 'bg-emerald-700';
            setText('v-name', v.name);
            setText('v-id', 'ID Number: ' + v.id);
            presence.classList.remove('hidden');
            presence.innerText = v.inside ? 'Timed In' : 'Timed Out';
            presence.className = 'shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-full border ' +
                (v.inside ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200');
            setText('v-category', v.category);
            setText('v-college', v.college);
            setText('v-detail-label', v.detail_label);
            setText('v-detail', v.detail);
            setText('v-last-action', v.last_action || 'No record yet');
            setText('v-last-time', v.last_timestamp || '-');
            inBtn.disabled = actionBusy || !v.can_time_in;
            outBtn.disabled = actionBusy || !v.can_time_out;
        }

        function applyStatus(data) {
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
            
            panel.className = `rounded-xl border px-4 py-3 text-center text-sm font-medium transition-colors duration-300 ${bgClass} ${textClass} ${borderClass}`;
            
            const regBtn = document.getElementById('register-btn');
            if (data.unknown_detected) {
                regBtn.classList.remove('hidden');
            } else {
                regBtn.classList.add('hidden');
            }

            renderVisitor(data.visitor);
            handleCameraVisibility(data.face_detected);
        }

        function handleCameraVisibility(faceDetected) {
            const standbyContainer = document.getElementById('standby-container');

            if (faceDetected) {
                lastFaceTime = Date.now();
                if (isCameraHidden) {
                    isCameraHidden = false;
                    standbyContainer.classList.add('hidden');
                }
            } else if (!isCameraHidden && Date.now() - lastFaceTime >= 5000) {
                isCameraHidden = true;
                standbyContainer.classList.remove('hidden');
            }
        }

        async function recordAttendance(action) {
            if (actionBusy) return;
            actionBusy = true;
            document.getElementById('time-in-btn').disabled = true;
            document.getElementById('time-out-btn').disabled = true;

            const body = new FormData();
            body.append('client_id', clientId);
            body.append('action', action);

            try {
                const res = await fetch('/attendance', { method: 'POST', body: body });
                const data = await res.json().catch(() => ({}));
                const ok = res.ok && data.success !== false;
                showToast(data.message || (ok ? action + ' recorded.' : 'Could not record ' + action + '. Please try again.'), ok ? 'success' : 'error');
            } catch (e) {
                showToast('An unexpected network error occurred. Please try again.', 'error');
            } finally {
                actionBusy = false;
            }
        }

        const clientId = (function () {
            let id = null;
            try { id = sessionStorage.getItem('gg_client_id'); } catch (e) {}
            if (!id) {
                id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
                try { sessionStorage.setItem('gg_client_id', id); } catch (e) {}
            }
            return id;
        })();

        const video = document.getElementById('webcam');
        const overlay = document.getElementById('overlay');
        const sampler = document.createElement('canvas');
        const ANALYZE_INTERVAL_MS = 450;
        const SAMPLE_WIDTH = 960;
        const BOX_COLORS = { green: '#22c55e', red: '#e11d48', amber: '#f59e0b' };

        function showCameraError(message) {
            document.getElementById('status-panel').innerText = message;
            showToast(message, 'error', 8000);
        }

        async function startCamera() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showCameraError('Camera is not available. Open this page over HTTPS in a modern browser.');
                return;
            }
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 }, aspectRatio: { ideal: 16 / 9 } },
                    audio: false
                });
                video.srcObject = stream;
                await video.play();

                // Some webcams start digitally zoomed in; drop to the widest field of view they allow
                try {
                    const track = stream.getVideoTracks()[0];
                    const caps = track.getCapabilities ? track.getCapabilities() : {};
                    if (caps.zoom) await track.applyConstraints({ advanced: [{ zoom: caps.zoom.min }] });
                } catch (e) {}
                analyzeLoop();
            } catch (err) {
                if (err && err.name === 'NotAllowedError') {
                    showCameraError('Camera permission was denied. Allow camera access and reload the page.');
                } else if (err && err.name === 'NotFoundError') {
                    showCameraError('No camera was found on this device.');
                } else {
                    showCameraError('Could not start the camera: ' + (err && err.message ? err.message : err));
                }
            }
        }

        function captureFrame() {
            const vw = video.videoWidth;
            const vh = video.videoHeight;
            if (!vw || !vh) return Promise.resolve(null);

            const scale = Math.min(1, SAMPLE_WIDTH / vw);
            sampler.width = Math.round(vw * scale);
            sampler.height = Math.round(vh * scale);

            const ctx = sampler.getContext('2d');
            ctx.save();
            ctx.translate(sampler.width, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(video, 0, 0, sampler.width, sampler.height);
            ctx.restore();

            return new Promise(resolve => sampler.toBlob(resolve, 'image/jpeg', 0.92));
        }

        async function sendFrame() {
            const blob = await captureFrame();
            if (!blob) return;

            const body = new FormData();
            body.append('client_id', clientId);
            body.append('frame', blob, 'frame.jpg');

            const res = await fetch('/analyze', { method: 'POST', body: body });
            if (!res.ok) return;

            const data = await res.json();
            applyStatus(data);
            drawOverlay(data.boxes || (data.box ? [data.box] : []));
        }

        async function analyzeLoop() {
            while (true) {
                const started = Date.now();
                try { await sendFrame(); } catch (e) {}
                const wait = Math.max(0, ANALYZE_INTERVAL_MS - (Date.now() - started));
                await new Promise(resolve => setTimeout(resolve, wait));
            }
        }

        function drawOverlay(boxes) {
            const w = overlay.clientWidth;
            const h = overlay.clientHeight;
            if (overlay.width !== w) overlay.width = w;
            if (overlay.height !== h) overlay.height = h;

            const ctx = overlay.getContext('2d');
            ctx.clearRect(0, 0, w, h);
            if (!boxes || !boxes.length || !w || !h || !video.videoWidth) return;

            boxes.forEach(function (box) {
            const vw = video.videoWidth;
            const vh = video.videoHeight;
            const scale = Math.min(w / vw, h / vh);
            const offsetX = (w - vw * scale) / 2;
            const offsetY = (h - vh * scale) / 2;
            const x = offsetX + box.x * vw * scale;
            const y = offsetY + box.y * vh * scale;
            const bw = box.w * vw * scale;
            const bh = box.h * vh * scale;
            const color = BOX_COLORS[box.color] || BOX_COLORS.amber;

            ctx.lineWidth = 2;
            ctx.strokeStyle = color;
            ctx.strokeRect(x, y, bw, bh);

            if (box.progress !== null && box.progress !== undefined) {
                ctx.fillStyle = 'rgba(40, 40, 40, 0.9)';
                ctx.fillRect(x, y + bh + 8, bw, 7);
                ctx.fillStyle = color;
                ctx.fillRect(x, y + bh + 8, bw * box.progress, 7);
            }

            if (box.label) {
                ctx.font = '600 13px sans-serif';
                ctx.fillStyle = color;
                ctx.fillText(box.label, x, Math.max(18, y - 8));
            }
            });
        }

        startCamera();

        const regVideo = document.getElementById('reg-video');
        const regPreview = document.getElementById('reg-preview');

        function setSubmitEnabled() {
            document.getElementById('submit-btn').disabled = !capturedBlob;
        }

        function resetCapture() {
            if (capturedUrl) {
                URL.revokeObjectURL(capturedUrl);
                capturedUrl = null;
            }
            capturedBlob = null;
            regPreview.removeAttribute('src');
            regPreview.classList.add('hidden');
            regVideo.classList.remove('hidden');

            const captureBtn = document.getElementById('capture-btn');
            captureBtn.classList.remove('hidden');
            captureBtn.disabled = false;
            captureBtn.innerText = 'Capture Photo';
            document.getElementById('retake-btn').classList.add('hidden');

            const hint = document.getElementById('capture-hint');
            hint.innerText = 'Face the camera in good light, then press Capture Photo.';
            hint.className = 'mt-2 text-[11px] font-medium text-emerald-800/80';
            setSubmitEnabled();
        }

        async function captureFace() {
            const btn = document.getElementById('capture-btn');
            btn.disabled = true;
            btn.innerText = 'Checking photo...';

            try {
                const blob = await captureFrame();
                if (!blob) {
                    showToast('The camera is not ready yet. Please try again.', 'warning');
                    return;
                }

                const body = new FormData();
                body.append('frame', blob, 'face.jpg');
                const res = await fetch('/check-face', { method: 'POST', body: body });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.ok) {
                    showToast(data.message || 'Could not use that photo. Please try again.', 'warning');
                    return;
                }

                capturedBlob = blob;
                capturedUrl = URL.createObjectURL(blob);
                regPreview.src = capturedUrl;
                regPreview.classList.remove('hidden');
                regVideo.classList.add('hidden');
                btn.classList.add('hidden');
                document.getElementById('retake-btn').classList.remove('hidden');

                const hint = document.getElementById('capture-hint');
                hint.innerText = 'Photo captured. If your face is not clear, press Retake.';
                hint.className = 'mt-2 text-[11px] font-semibold text-emerald-800';
                setSubmitEnabled();
            } catch (e) {
                showToast('A network error occurred while checking the photo. Please try again.', 'error');
            } finally {
                btn.disabled = false;
                btn.innerText = 'Capture Photo';
            }
        }

        function retakeFace() {
            resetCapture();
        }

        function openModal() {
            document.getElementById('cancel-confirm-box').classList.add('hidden');
            regVideo.srcObject = video.srcObject;
            regVideo.play().catch(() => {});
            resetCapture();
            document.getElementById('reg-modal').classList.remove('hidden');
        }

        function hideModal() {
            document.getElementById('reg-modal').classList.add('hidden');
            document.getElementById('reg-form').reset();
            handleUserTypeChange('Student');
            regVideo.srcObject = null;
            resetCapture();
        }
        
        function closeModal() { 
            const form = document.getElementById('reg-form');
            const hasData = capturedBlob !== null || Array.from(form.elements).some(input => 
                (input.type === 'text' || input.type === 'number') && input.value.trim() !== ''
            );
            
            if (hasData) {
                document.getElementById('cancel-confirm-box').classList.remove('hidden');
            } else {
                hideModal();
            }
        }

        function dismissConfirmClose(confirmCancel) {
            document.getElementById('cancel-confirm-box').classList.add('hidden');
            if (confirmCancel) {
                hideModal();
            }
        }

        function submitRegistration(event) {
            event.preventDefault();
            if (!capturedBlob) {
                showToast('Capture your face photo before submitting.', 'warning');
                return;
            }

            const form = document.getElementById('reg-form');
            const formData = new FormData(form);
            formData.append('frame', capturedBlob, 'face.jpg');
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
                    hideModal();
                } else {
                    showToast(data.message || 'Registration failed. Please check the required fields.', 'error');
                }
                btn.innerHTML = originalBtnHtml;
                setSubmitEnabled();
            })
            .catch(() => {
                showToast('An unexpected network error occurred. Please try again.', 'error');
                btn.innerHTML = originalBtnHtml;
                setSubmitEnabled();
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
            <a href="{{ url_for('login_page') }}" class="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-800 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-3 py-1.5 rounded-lg transition-colors mb-5"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7"></path></svg>Back</a>
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

def face_problem(frame):
    boxes = detect_faces(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    if not boxes:
        return "No clear face found in the captured frame. Face the camera in good light and try again."
    if len(boxes) > 1 and boxes[1][2] * boxes[1][3] > 0.5 * boxes[0][2] * boxes[0][3]:
        return "More than one face is in the frame. Only the person registering should be in front of the camera."
    return None

@app.route('/check-face', methods=['POST'])
def check_face():
    upload = request.files.get('frame')
    if upload is None:
        return jsonify({"ok": False, "message": "No photo received."}), 400

    frame = cv2.imdecode(np.frombuffer(upload.read(), np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"ok": False, "message": "Invalid image."}), 400

    try:
        problem = face_problem(frame)
    except Exception as e:
        logging.error(f"Face check error: {e}")
        return jsonify({"ok": False, "message": "Could not check the photo. Please try again."}), 500

    if problem:
        return jsonify({"ok": False, "message": problem})
    return jsonify({"ok": True})

@app.route('/attendance', methods=['POST'])
def attendance():
    client_id = request.form.get('client_id', '').strip()[:64]
    action = request.form.get('action', '').strip()
    if not client_id or action not in ('Time In', 'Time Out'):
        return jsonify({"success": False, "message": "Invalid request."}), 400

    state = get_client_state(client_id)
    current = state["current"]
    visitor = current["visitor"]
    now = time.time()

    if visitor is None or not current["verified"] or now - current["seen"] > ATTENDANCE_GRACE:
        return jsonify({"success": False, "message": "Face not verified. Hold still in front of the camera first."}), 400

    s_id = visitor["Student_ID"]
    if now < state["cooldowns"].get(s_id, 0):
        return jsonify({"success": False, "message": "Already recorded. Please wait a few seconds."}), 400

    try:
        ok, message = record_attendance(visitor, action)
    except Exception as e:
        logging.error(f"Error processing attendance in Supabase: {e}")
        return jsonify({"success": False, "message": f"Could not record attendance for {pretty_name(visitor['Name'])}. Please try again."}), 500

    if not ok:
        return jsonify({"success": False, "message": message}), 400

    category, college, detail_label, detail = describe_visitor(visitor)
    clean_course = detail.split(" - Year")[0] if " - Year" in detail else detail
    system_status = state["system_status"]
    system_status["text"] = f"SUCCESS ({action}): {pretty_name(visitor['Name'])} | ID: {s_id} | {clean_course}"
    system_status["status"] = "success"
    system_status["unknown_detected"] = False

    now = time.time()
    state["cooldown_timer"] = now + COOLDOWN_SECONDS
    state["cooldowns"][s_id] = now + COOLDOWN_SECONDS
    state["cooldowns"] = {k: v for k, v in state["cooldowns"].items() if v > now}
    state["presence"]["id"] = None

    return jsonify({"success": True, "message": message})

@app.route('/analyze', methods=['POST'])
def analyze():
    client_id = request.form.get('client_id', '').strip()[:64]
    upload = request.files.get('frame')
    if not client_id or upload is None:
        return jsonify({"error": "Missing frame or client id."}), 400

    frame = cv2.imdecode(np.frombuffer(upload.read(), np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "Invalid image."}), 400

    ensure_recognizer_fresh()

    try:
        state = get_client_state(client_id)
        return jsonify(analyze_frame(frame, state))
    except Exception as e:
        logging.error(f"Frame analysis error: {e}")
        return jsonify({"error": "Frame analysis failed."}), 500

@app.route('/register', methods=['POST'])
def register():
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
            course = f"{faculty_college} - {department}"

        elif user_type == 'Others':
            address = request.form.get('other_address', '').strip() or "Visitor"
            student_id = f"OTH-{short_id}"
            college = "Others"
            course = address

        else:  # Student
            student_id = request.form.get('student_id', '').strip()
            college = request.form.get('college', '').strip()
            program = request.form.get('course', '').strip().upper()
            year_level = request.form.get('year_level', '').strip()

            if not student_id or not college or not program or not year_level:
                return jsonify({"success": False, "message": "Student ID, College, Course, and Year Level are required!"}), 400
            if year_level not in ('1', '2', '3', '4'):
                return jsonify({"success": False, "message": "Year Level must be between 1 and 4!"}), 400

            course = f"{program} - Year {year_level}"

        # 1. Manual check kung existing na ang ID
        existing_check = supabase.table("visitors").select("student_id").eq("student_id", student_id).execute()
        if existing_check.data:
            return jsonify({"success": False, "message": "Already Exist"}), 400

        upload = request.files.get('frame')
        if upload is None:
            return jsonify({"success": False, "message": "A face photo is required. Capture your face before submitting."}), 400

        captured_frame = cv2.imdecode(np.frombuffer(upload.read(), np.uint8), cv2.IMREAD_COLOR)
        if captured_frame is None:
            return jsonify({"success": False, "message": "Failed to process image frame."}), 400

        problem = face_problem(captured_frame)
        if problem:
            return jsonify({"success": False, "message": problem}), 400

        normalized_name = f"{surname}, {fname}, {mname or 'N/A'}, {suffix}"
        
        success, encoded_img = cv2.imencode('.jpg', captured_frame)
        if not success:
            return jsonify({"success": False, "message": "Failed to process image frame."}), 500
        
        img_bytes = encoded_img.tobytes()
        file_path_storage = f"{student_id}.jpg"

        supabase.storage.from_("faces").upload(
            path=file_path_storage, 
            file=img_bytes, 
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )

        with open(os.path.join(FACE_DIR, file_path_storage), "wb") as f:
            f.write(img_bytes)

        public_url = supabase.storage.from_("faces").get_public_url(file_path_storage)

        supabase.table("visitors").insert({
            "student_id": student_id,
            "normalized_name": normalized_name,
            "college": college,
            "course_year": course,
            "image_path": public_url
        }).execute()

        load_recognizer_training()

        return jsonify({
            "success": True, 
            "message": f"Successfully registered {normalized_name} ({user_type}). Face the camera and press Time In to record attendance."
        })
    except Exception as e:
        error_str = str(e)
        # 2. Sisiguraduhing "Already Exist" ang lalabas kapag na-trigger ang unique key constraint
        if "duplicate key" in error_str.lower() or "visitors_pkey" in error_str.lower() or "already exists" in error_str.lower():
            return jsonify({"success": False, "message": "Already Exist"}), 400
            
        logging.error(f"Registration save error: {e}")
        return jsonify({"success": False, "message": f"Failed to register visitor: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)