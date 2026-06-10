import cv2
import os
import sys
from database import get_student, init_db
from encoder import encode_student_faces

def run_capture(student_id):
    """
    Launches the OpenCV webcam window on the host, captures 20 face images,
    and runs the encoder. Returns (success_boolean, status_message).
    """
    student_id = student_id.strip()
    if not student_id:
        return False, "Student ID cannot be empty."
        
    # Check if student exists in SQLite
    student = get_student(student_id)
    if not student:
        return False, f"Student ID '{student_id}' is not registered in the database."
        
    print(f"[+] Found Student: {student['name']} ({student['department']})")
    
    # Create dataset directory
    dataset_dir = os.path.join(os.path.dirname(__file__), 'dataset', student_id)
    os.makedirs(dataset_dir, exist_ok=True)
    
    # Initialize camera
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW) # Use DirectShow on Windows for faster startup
    if not cam.isOpened():
        # Fallback to default backend if DirectShow fails
        cam = cv2.VideoCapture(0)
        
    if not cam.isOpened():
        return False, "Could not access the laptop camera."
        
    # Set webcam resolution to widescreen HD (1280x720)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
    # Load face cascade
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if face_cascade.empty():
        cam.release()
        return False, "Could not load Haar Cascade XML for face detection."

    print("\n[Instructions]")
    print(" - Look straight into the camera.")
    print(" - Press SPACEBAR to capture an image.")
    print(" - Try different head angles, lighting, and expressions.")
    print(" - Press 'q' to quit.")
    print("==================================================\n")
    
    count = 0
    max_images = 20
    
    while True:
        ret, frame = cam.read()
        if not ret:
            print("[-] Error: Failed to grab frame.")
            break
            
        # Flip the frame horizontally for mirror effect
        frame = cv2.flip(frame, 1)
        
        # Create a copy of the raw frame (without bounding boxes or overlays)
        clean_frame = frame.copy()
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5,
            minSize=(100, 100)
        )
        
        # Draw bounding boxes
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (46, 204, 113), 2) # Emerald green box
            # Draw overlay text showing capture status
            cv2.putText(
                frame, 
                f"Face Detected. Captured: {count}/{max_images}", 
                (x, y-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.55, 
                (46, 204, 113), 
                2
            )
            
        # Add visual overlay instructions on the frame
        cv2.putText(
            frame, 
            "Press [SPACE] to capture | [q] to exit", 
            (20, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (243, 156, 18), 
            2
        )
        
        # Display the live video feed
        cv2.imshow("Capture Dataset - Press SPACE to Save Image", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            # Save frame if a face is detected
            if len(faces) == 0:
                print("[-] No face detected in the frame. Move closer or adjust lighting.")
                continue
                
            count += 1
            img_path = os.path.join(dataset_dir, f"{student_id}_{count}.jpg")
            
            # Save the clean frame (without bounding boxes)
            cv2.imwrite(img_path, clean_frame)
            print(f"[+] Saved {img_path}")
            
            if count >= max_images:
                print(f"[+] Successfully captured {max_images} images.")
                break
                
        elif key == ord('q'):
            print("[*] Capture process stopped by user.")
            break
            
    # Clean up
    cam.release()
    cv2.destroyAllWindows()
    
    if count > 0:
        print("\n[*] Initializing face encoder to register encodings in the database...")
        success, message = encode_student_faces(student_id)
        if success:
            return True, f"Successfully captured {count} images and registered encodings. {message}"
        else:
            return False, f"Captured images, but encoding failed: {message}"
    else:
        return False, "No images captured. Student not encoded."

def capture_dataset():
    # Initialize DB in case it's not run yet
    init_db()

    print("==================================================")
    print("      STUDENT FACE DATASET CAPTURE SCRIPT         ")
    print("==================================================")
    
    student_id = input("Enter Student ID: ").strip()
    success, message = run_capture(student_id)
    if success:
        print(f"[+] Success: {message}")
    else:
        print(f"[-] Error: {message}")

if __name__ == '__main__':
    capture_dataset()
