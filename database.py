import sqlite3
import json
import werkzeug.security as security
from config import Config

def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        student_id_number TEXT UNIQUE,
        grade_level TEXT,
        homeroom_teacher_id INTEGER,
        homeroom_classroom_id INTEGER,
        department TEXT,
        office_location TEXT,
        contact_phone TEXT,
        office_hours TEXT,
        assigned_homeroom_classroom_id INTEGER
    )
    ''')

    # Rooms Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        location TEXT NOT NULL,
        teacher_in_charge_id INTEGER NOT NULL,
        qr_pin TEXT NOT NULL DEFAULT '1234',
        requires_after_hours_only INTEGER NOT NULL DEFAULT 0,
        description TEXT,
        icon TEXT,
        extra_data TEXT
    )
    ''')

    # Bookings Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        primary_student_id INTEGER NOT NULL,
        co_booker_ids TEXT,
        room_id INTEGER NOT NULL,
        booking_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        purpose TEXT NOT NULL,
        teacher_in_charge_id INTEGER NOT NULL,
        homeroom_teacher_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        checked_in_at TEXT,
        checked_in_by_student_id INTEGER,
        checked_out_at TEXT,
        grace_period_extended INTEGER DEFAULT 0,
        prompt_sent_at TEXT,
        extension_status TEXT DEFAULT 'NONE',
        extension_minutes INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (primary_student_id) REFERENCES users (id),
        FOREIGN KEY (room_id) REFERENCES rooms (id)
    )
    ''')

    # Notifications Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'INFO',
        booking_id INTEGER,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    conn.commit()
    seed_demo_data(conn)
    conn.close()

def seed_demo_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        return # Already seeded

    default_pw = security.generate_password_hash("password123")

    # 1. Teachers
    teachers = [
        # id=1: Dr. Aris Thorne (Physics TIC)
        ("Dr. Aris Thorne", "thorne@school.edu", default_pw, "teacher", None, None, None, None, "Physics Department", "Science Hall 201", "Ext. 4101", "Mon-Fri 14:00 - 16:00", None),
        # id=2: Ms. Elena Rostova (Chemistry/Bio/Lang Lab TIC)
        ("Ms. Elena Rostova", "rostova@school.edu", default_pw, "teacher", None, None, None, None, "Chemistry & Life Sciences", "Science Hall 105", "Ext. 4105", "Mon-Thu 13:00 - 15:00", None),
        # id=3: Mr. David Chen (Homeroom Teacher Class 10-A)
        ("Mr. David Chen", "chen@school.edu", default_pw, "teacher", None, None, None, None, "Mathematics Department", "Main Building 302", "Ext. 4302", "Daily 15:30 - 16:30", None),
        # id=4: Mrs. Sarah Jenkins (Homeroom Teacher Class 10-B)
        ("Mrs. Sarah Jenkins", "jenkins@school.edu", default_pw, "teacher", None, None, None, None, "Language Arts", "Humanities Wing 110", "Ext. 4210", "Mon/Wed/Fri 15:00 - 16:00", None),
        # id=5: Coach Marcus Vance (Sports Courts TIC)
        ("Coach Marcus Vance", "vance@school.edu", default_pw, "teacher", None, None, None, None, "Physical Education", "Gymnasium Office 1", "Ext. 4500", "Daily 14:00 - 17:00", None),
        # id=6: Mr. Alex Rivera (Media, Esports, Podcast TIC)
        ("Mr. Alex Rivera", "rivera@school.edu", default_pw, "teacher", None, None, None, None, "Digital Media & Tech", "Innovation Hub 204", "Ext. 4888", "Tue-Thu 15:00 - 17:00", None),
    ]

    for t in teachers:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, role, student_id_number, grade_level, 
                           homeroom_teacher_id, homeroom_classroom_id, department, office_location, 
                           contact_phone, office_hours, assigned_homeroom_classroom_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', t)

    # 2. Rooms - Classrooms & Facilities
    # We will create Classrooms first so we can assign Homeroom Teachers
    rooms_data = [
        # Facilities
        ("Physics Laboratory", "science_lab", 30, "Science Hall 2nd Floor", 1, "2026", 0, "Advanced physics experimental lab with precision laser tables and mechanics gear.", "flask", json.dumps({"lab_type": "Physics", "safety_guidelines": "Safety goggles required. No food or drinks."})),
        ("Chemistry Laboratory", "science_lab", 32, "Science Hall 1st Floor", 2, "3045", 0, "Fume hoods, Bunsen burners, and titration stations.", "flask", json.dumps({"lab_type": "Chemistry", "safety_guidelines": "Lab coat and goggles mandatory."})),
        ("Biology Laboratory", "science_lab", 28, "Science Hall 1st Floor", 2, "4089", 0, "High-resolution optical microscopes and specimen collections.", "flask", json.dumps({"lab_type": "Biology", "safety_guidelines": "Wash hands before and after sessions."})),
        ("Language Laboratory", "science_lab", 25, "Humanities Wing 102", 4, "1122", 0, "Acoustic audio booths with digital language learning software.", "headphones", json.dumps({"lab_type": "Language", "safety_guidelines": "Use provided alcohol wipes on headsets."})),
        
        ("Auditorium", "event_space", 350, "Main Campus Center", 3, "9900", 0, "Grand stage, surround audio system, and theatrical lighting system.", "theater-masks", json.dumps({"capacity_rules": "Requires AV technician approval for lighting control."})),
        ("Library Conference Room", "event_space", 16, "Central Library 2nd Floor", 4, "7766", 0, "Quiet glass enclosure with conference camera and whiteboard.", "book-reader", json.dumps({})),
        
        ("Podcast Recording Studio", "media_room", 6, "Innovation Hub 201", 6, "8811", 0, "Soundproof recording studio with Shure SM7B mics and Rodecaster Pro.", "podcast", json.dumps({"equipment": ["Rodecaster Pro", "Shure SM7B Mics x4", "Headphone Distribution Amp"]})),
        ("Audiovisual Production Room", "media_room", 12, "Innovation Hub 202", 6, "8822", 0, "4K video editing suite with DaVinci Resolve and green screen booth.", "film", json.dumps({"equipment": ["Green Screen Studio", "4K Video Editing Rig", "Studio Softlights"]})),
        ("Esports & Gaming Room", "media_room", 20, "Student Union 3rd Floor", 6, "8833", 0, "High-performance PC rigs, 240Hz monitors, and team shoutcaster booth.", "gamepad", json.dumps({"equipment": ["240Hz Gaming PCs x10", "Console Gaming Station", "Shoutcaster Desk"]})),
        
        ("Basketball Court (Indoor)", "sports_facility", 40, "Gymnasium Main Hall", 5, "5511", 0, "Hardwood maple court with digital scoreboard.", "basketball-ball", json.dumps({})),
        ("Volleyball Court (Indoor)", "sports_facility", 30, "Gymnasium Court B", 5, "5522", 0, "Regulation net setup with padded posts.", "volleyball-ball", json.dumps({})),
    ]

    for r in rooms_data:
        cursor.execute('''
        INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', r)

    # Add Classrooms (Class 10-A to Class 12-I, total 27 classes)
    # Assign Class 10-A to Mr. David Chen (teacher_id=3) and Class 10-B to Mrs. Sarah Jenkins (teacher_id=4)
    classroom_count = 0
    grades = ['10', '11', '12']
    sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']
    
    class_10a_room_id = None
    class_10b_room_id = None

    for g in grades:
        for s in sections:
            classroom_count += 1
            class_name = f"Class {g}-{s}"
            location = f"Academic Block {g}, Room {s}01"
            
            # Map TIC teacher: 10-A -> Mr. Chen (id=3), 10-B -> Mrs. Jenkins (id=4), others cycle teachers 1..6
            if g == '10' and s == 'A':
                tic_id = 3
            elif g == '10' and s == 'B':
                tic_id = 4
            else:
                tic_id = ((classroom_count - 1) % 6) + 1
                
            cursor.execute('''
            INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
            VALUES (?, 'classroom', 35, ?, ?, '1234', 1, 'Standard academic classroom available for study groups after 15:30.', 'chalkboard-teacher', ?)
            ''', (class_name, location, tic_id, json.dumps({"grade_level": f"Grade {g}", "assigned_homeroom_teacher_id": tic_id})))
            
            room_id = cursor.lastrowid
            if g == '10' and s == 'A':
                class_10a_room_id = room_id
                cursor.execute("UPDATE users SET assigned_homeroom_classroom_id = ? WHERE id = 3", (class_10a_room_id,))
            elif g == '10' and s == 'B':
                class_10b_room_id = room_id
                cursor.execute("UPDATE users SET assigned_homeroom_classroom_id = ? WHERE id = 4", (class_10b_room_id,))

    # 3. Students
    students = [
        # Alex Mercer (STU1001) - Homeroom Class 10-A (Teacher: Mr. David Chen id=3)
        ("Alex Mercer", "alex.mercer@school.edu", default_pw, "student", "STU1001", "Grade 10", 3, class_10a_room_id),
        # Maya Lin (STU1002) - Homeroom Class 10-A (Teacher: Mr. David Chen id=3)
        ("Maya Lin", "maya.lin@school.edu", default_pw, "student", "STU1002", "Grade 10", 3, class_10a_room_id),
        # Leo Tanaka (STU1003) - Homeroom Class 10-B (Teacher: Mrs. Sarah Jenkins id=4)
        ("Leo Tanaka", "leo.tanaka@school.edu", default_pw, "student", "STU1003", "Grade 10", 4, class_10b_room_id),
        # Chloe Bennett (STU1004) - Homeroom Class 10-B (Teacher: Mrs. Sarah Jenkins id=4)
        ("Chloe Bennett", "chloe.bennett@school.edu", default_pw, "student", "STU1004", "Grade 10", 4, class_10b_room_id),
        # Admin User
        ("System Admin", "admin@school.edu", default_pw, "admin", None, None, None, None)
    ]

    for s in students:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, role, student_id_number, grade_level, homeroom_teacher_id, homeroom_classroom_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', s)

    conn.commit()
