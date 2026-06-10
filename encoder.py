import os
import face_recognition
import numpy as np
from database import add_face_encoding, delete_face_encodings, get_student

DATASET_DIR = os.path.join(os.path.dirname(__file__), 'dataset')

def encode_student_faces(student_id):
    """
    Finds all face images in dataset/<student_id>/, extracts 128D face encodings,
    and stores them in the face_encodings database table.
    """
    student = get_student(student_id)
    if not student:
        return False, f"Student ID '{student_id}' does not exist in the database."
        
    student_dir = os.path.join(DATASET_DIR, student_id)
    if not os.path.exists(student_dir):
        return False, f"Dataset directory for student '{student_id}' not found."
        
    image_extensions = ('.jpg', '.jpeg', '.png')
    image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(image_extensions)]
    
    if not image_files:
        return False, f"No images found in dataset directory for student '{student_id}'."
        
    # Clear old encodings for this student to rebuild/update
    delete_face_encodings(student_id)
    
    successful_encodings = 0
    
    for img_name in image_files:
        img_path = os.path.join(student_dir, img_name)
        try:
            # Load the image
            image = face_recognition.load_image_file(img_path)
            
            # Find face encodings (assuming one face per image)
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) > 0:
                # Store the first detected face's encoding
                add_face_encoding(student_id, encodings[0])
                successful_encodings += 1
            else:
                print(f"Warning: No face detected in image {img_name}. Skipping.")
        except Exception as e:
            print(f"Error processing image {img_name}: {str(e)}")
            
    if successful_encodings > 0:
        return True, f"Successfully processed and stored {successful_encodings} face encodings for student '{student_id}'."
    else:
        return False, f"Failed to extract any face encodings for student '{student_id}'."

def encode_all_students():
    """
    Scans the entire dataset directory and encodes faces for all registered students.
    """
    if not os.path.exists(DATASET_DIR):
        return "Dataset directory does not exist."
        
    student_dirs = [d for d in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, d))]
    
    results = {}
    for student_id in student_dirs:
        success, message = encode_student_faces(student_id)
        results[student_id] = message
        print(f"[{student_id}] {message}")
        
    return results

if __name__ == '__main__':
    print("Scanning dataset and encoding all faces...")
    results = encode_all_students()
    print("Encoding complete.")
