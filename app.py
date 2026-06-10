from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import os
import face_recognition
import base64
from datetime import datetime

import database
from capture_dataset import run_capture

app = Flask(__name__)

# Cache for known face encodings and metadata to prevent excessive database reads during video stream
known_face_encodings = []
known_face_names = []
known_student_info = {} # student_id -> {"name": ..., "dept": ...}

# Track recently marked attendance in-memory to prevent spamming the database with duplicate queries
# format: {student_id: timestamp_seconds}
marked_cooldown = {}
COOLDOWN_SECONDS = 15

def reload_face_encodings():
    """Reloads encodings and student details from the database into memory."""
    global known_face_encodings, known_face_names, known_student_info
    try:
        encodings, student_ids = database.get_all_encodings()
        known_face_encodings = encodings
        known_face_names = student_ids
        
        # Load details for all students
        students = database.get_all_students()
        known_student_info = {
            s['student_id']: {"name": s['name'], "dept": s['department']} 
            for s in students
        }
        print(f"[+] Loaded {len(known_face_encodings)} face encodings into memory.")
    except Exception as e:
        print(f"[-] Error loading face encodings: {str(e)}")

# Initialize database and cache on startup
database.init_db()
reload_face_encodings()

def generate_frames():
    """Generates camera frames with face recognition overlay for Flask stream."""
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW) # Use DirectShow on Windows for faster startup
    if not camera.isOpened():
        camera = cv2.VideoCapture(0)
        
    if not camera.isOpened():
        print("[-] Error: Camera could not be opened for streaming.")
        return

    process_this_frame = True
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Mirror frame
        frame = cv2.flip(frame, 1)
        
        # Resize frame to 1/4 for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        face_locations = []
        face_names = []
        
        if process_this_frame:
            # Find face locations and encodings
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            for face_encoding in face_encodings:
                name = "Unknown"
                student_id = None
                
                if len(known_face_encodings) > 0:
                    # Compare face against all stored face encodings
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.45)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            student_id = known_face_names[best_match_index]
                            student = known_student_info.get(student_id)
                            if student:
                                name = f"{student['name']} ({student_id})"
                                
                                # Mark attendance if not in cooldown
                                current_time = datetime.now().timestamp()
                                last_marked = marked_cooldown.get(student_id, 0)
                                if current_time - last_marked > COOLDOWN_SECONDS:
                                    success_mark, msg = database.mark_attendance(student_id)
                                    if success_mark:
                                        print(f"[+] Attendance logged: {student['name']}")
                                    marked_cooldown[student_id] = current_time
                
                face_names.append(name)
                
        process_this_frame = not process_this_frame
        
        # Draw bounding boxes and details on original resolution frame
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            # Scale coordinates back up by 4
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            
            # Emerald green for recognized, Coral red for unknown
            is_known = name != "Unknown"
            color = (113, 204, 46) if is_known else (76, 76, 231) # BGR
            
            # Draw sleek face rectangle
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            
            # Draw label
            cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, name, (left + 6, bottom - 8), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
    camera.release()

# Web Application Routes
@app.route('/')
def dashboard():
    stats = database.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        department = request.form.get('department')
        email = request.form.get('email')
        
        if not student_id or not name or not department or not email:
            return jsonify({"success": False, "message": "All fields are required."}), 400
            
        success, message = database.add_student(student_id, name, department, email)
        if success:
            reload_face_encodings() # Refresh student maps
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message}), 400
            
    return render_template('register.html')

@app.route('/attendance')
def attendance():
    reload_face_encodings() # Reload encodings before starting attendance screen
    return render_template('attendance.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/logs')
def logs():
    filter_date = request.args.get('date', '')
    search_query = request.args.get('search', '')
    attendance_logs = database.get_attendance_logs(filter_date or None, search_query or None)
    return render_template('logs.html', logs=attendance_logs, selected_date=filter_date, search_query=search_query)

# AJAX API Routes
@app.route('/api/stats')
def api_stats():
    return jsonify(database.get_dashboard_stats())

@app.route('/api/reload_encodings', methods=['POST'])
def api_reload_encodings():
    reload_face_encodings()
    return jsonify({"success": True, "message": "Face encodings reloaded successfully."})

@app.route('/api/students')
def api_students():
    students = database.get_all_students()
    return jsonify([dict(s) for s in students])

@app.route('/api/start_capture', methods=['POST'])
def api_start_capture():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({"success": False, "message": "Student ID is required."}), 400
        
    # Run the OpenCV capture window on host
    success, message = run_capture(student_id)
    if success:
        reload_face_encodings() # Reload encodings to cache them in app
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message})

@app.route('/api/upload_capture', methods=['POST'])
def api_upload_capture():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    image_data = data.get('image')
    
    if not student_id or not image_data:
        return jsonify({"success": False, "message": "Student ID and image data are required."}), 400
        
    try:
        # Decode base64 image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        decoded = base64.b64decode(image_data)
        nparr = np.frombuffer(decoded, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"success": False, "message": "Failed to decode image."}), 400
            
        # Detect face to verify a face is present
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5, minSize=(80, 80))
        
        if len(faces) == 0:
            return jsonify({"success": False, "message": "No face detected. Adjust your position."})
            
        # Save image
        dataset_dir = os.path.join(os.path.dirname(__file__), 'dataset', student_id)
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Count existing images to get next number
        existing_files = [f for f in os.listdir(dataset_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        next_index = len(existing_files) + 1
        
        img_path = os.path.join(dataset_dir, f"{student_id}_{next_index}.jpg")
        cv2.imwrite(img_path, img)
        
        return jsonify({
            "success": True, 
            "message": "Frame captured.", 
            "count": next_index
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/train_student', methods=['POST'])
def api_train_student():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    if not student_id:
        return jsonify({"success": False, "message": "Student ID is required."}), 400
        
    try:
        from encoder import encode_student_faces
        success, message = encode_student_faces(student_id)
        if success:
            reload_face_encodings() # Refresh student maps in app cache
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": f"Training error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
