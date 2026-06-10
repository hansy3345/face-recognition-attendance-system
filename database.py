import sqlite3
import os
import numpy as np
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create face encodings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            encoding BLOB NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE
        )
    ''')
    
    # Create attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE,
            UNIQUE(student_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()

# Student operations
def add_student(student_id, name, department, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO students (student_id, name, department, email) VALUES (?, ?, ?, ?)",
            (student_id.strip(), name.strip(), department.strip(), email.strip())
        )
        conn.commit()
        return True, "Student registered successfully."
    except sqlite3.IntegrityError:
        return False, f"Student ID '{student_id}' already exists."
    finally:
        conn.close()

def get_student(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    conn.close()
    return student

def get_all_students():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    conn.close()
    return students

# Encoding operations
def add_face_encoding(student_id, encoding_np):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Serialize numpy array to bytes
    encoding_bytes = encoding_np.tobytes()
    cursor.execute(
        "INSERT INTO face_encodings (student_id, encoding) VALUES (?, ?)",
        (student_id, encoding_bytes)
    )
    conn.commit()
    conn.close()

def delete_face_encodings(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM face_encodings WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()

def get_all_encodings():
    conn = get_db_connection()
    rows = conn.execute("SELECT student_id, encoding FROM face_encodings").fetchall()
    conn.close()
    
    encodings_list = []
    names_list = []
    
    for row in rows:
        student_id = row['student_id']
        # Convert bytes back to numpy float64 array
        encoding = np.frombuffer(row['encoding'], dtype=np.float64)
        encodings_list.append(encoding)
        names_list.append(student_id)
        
    return encodings_list, names_list

# Attendance operations
def mark_attendance(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    
    try:
        # Check if student exists
        student = cursor.execute("SELECT name FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if not student:
            return False, "Student not found."
            
        cursor.execute(
            "INSERT INTO attendance (student_id, date, time, status) VALUES (?, ?, ?, ?)",
            (student_id, current_date, current_time, "Present")
        )
        conn.commit()
        return True, f"Attendance marked for {student['name']}."
    except sqlite3.IntegrityError:
        # Unique constraint fails if already marked present today
        return False, "Attendance already marked for today."
    finally:
        conn.close()

def get_attendance_logs(filter_date=None, search_query=None):
    conn = get_db_connection()
    query = """
        SELECT a.id, a.student_id, s.name, s.department, s.email, a.date, a.time, a.status 
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
    """
    params = []
    conditions = []
    
    if filter_date:
        conditions.append("a.date = ?")
        params.append(filter_date)
        
    if search_query:
        conditions.append("(s.name LIKE ? OR s.student_id LIKE ? OR s.department LIKE ?)")
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY a.date DESC, a.time DESC"
    
    logs = conn.execute(query, params).fetchall()
    conn.close()
    return logs

def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_students = cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present_today = cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,)).fetchone()[0]
    
    # Get last 5 logs
    recent_logs = cursor.execute("""
        SELECT a.student_id, s.name, s.department, a.time 
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date = ?
        ORDER BY a.time DESC
        LIMIT 5
    """, (today,)).fetchall()
    
    conn.close()
    
    absent_today = max(0, total_students - present_today)
    attendance_rate = 0
    if total_students > 0:
        attendance_rate = round((present_today / total_students) * 100)
        
    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "attendance_rate": attendance_rate,
        "recent_logs": recent_logs
    }

# Run database initialization
if __name__ == '__main__':
    init_db()
    print("Database initialized.")
