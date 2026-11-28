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

    init_booking_history(conn)
    conn.commit()
    seed_demo_data(conn)
    conn.close()

def trim_personal_bookings(conn, user_id):
    conn.execute("""
        DELETE FROM bookings
        WHERE status IN ('COMPLETED','REJECTED','EXPIRED','CANCELLED')
          AND id IN (SELECT id FROM bookings WHERE primary_student_id = ?
                     ORDER BY id DESC LIMIT -1 OFFSET 5)
    """, (user_id,))


def init_booking_history(conn):
    conn.execute("BEGIN IMMEDIATE")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pic_history'").fetchone():
        return

    conn.execute("""
        CREATE TABLE pic_history (
            id INTEGER PRIMARY KEY, booking_id INTEGER NOT NULL UNIQUE,
            pic_id INTEGER NOT NULL, booker_id INTEGER NOT NULL, room_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            decision TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX pic_history_recent ON pic_history(pic_id, id DESC)")
    conn.execute("""
        CREATE TRIGGER trim_pic_history AFTER INSERT ON pic_history BEGIN
            DELETE FROM pic_history WHERE id IN (
                SELECT id FROM pic_history WHERE pic_id = NEW.pic_id
                ORDER BY id DESC LIMIT -1 OFFSET 25
            );
        END
    """)
    conn.execute("""
        CREATE TRIGGER record_pic_decision AFTER UPDATE OF status ON bookings
        WHEN OLD.status = 'PENDING' AND NEW.status IN ('APPROVED','REJECTED') BEGIN
            INSERT INTO pic_history (booking_id,pic_id,booker_id,room_id,booking_date,start_time,end_time,decision)
            VALUES (NEW.id,NEW.teacher_in_charge_id,NEW.primary_student_id,NEW.room_id,
                    NEW.booking_date,NEW.start_time,NEW.end_time,NEW.status);
        END
    """)
    # Existing decisions precede the new log. Use the recorded decision notification
    # time where available, including bookings that have since finished.
    conn.execute("""
        INSERT INTO pic_history (booking_id,pic_id,booker_id,room_id,booking_date,start_time,end_time,decision)
        SELECT b.id,b.teacher_in_charge_id,b.primary_student_id,b.room_id,b.booking_date,b.start_time,b.end_time,
               CASE WHEN b.status='REJECTED' OR n.title='Booking Declined' THEN 'REJECTED' ELSE 'APPROVED' END
        FROM bookings b LEFT JOIN notifications n ON n.id = (
            SELECT MAX(id) FROM notifications WHERE booking_id=b.id AND type='STATUS_UPDATE'
                AND title IN ('Booking Approved!', 'Booking Declined')
        )
        WHERE n.id IS NOT NULL OR b.status IN ('APPROVED','REJECTED','CHECKED_IN','COMPLETED','PENDING_CONFIRMATION','EXPIRED')
        ORDER BY COALESCE(n.created_at,b.created_at), b.id
    """)
    for row in conn.execute("SELECT DISTINCT primary_student_id FROM bookings").fetchall():
        trim_personal_bookings(conn, row[0])


def seed_demo_data(conn, force=False):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM rooms WHERE category = 'classroom'")
    classroom_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count > 0 and classroom_count == 9 and not force:
        return # Already seeded with exactly 9 classrooms

    default_pw = security.generate_password_hash("password123")

    # If force or upgrading: clear bookings, users, rooms safely
    if force or user_count > 0:
        cursor.execute("DELETE FROM pic_history")
        cursor.execute("DELETE FROM bookings")
        cursor.execute("DELETE FROM notifications")
        cursor.execute("DELETE FROM rooms")
        cursor.execute("DELETE FROM users")
        conn.commit()

    # 1. Teachers (15 dedicated teachers with complete contact & room assignment)
    teachers = [
        # 1. Dr. Yohanes Aris Thorne
        ("Dr. Yohanes Aris Thorne, M.Pd.", "teacher1@example.com", default_pw, "teacher",
         "Physics & Applied Science", "Laboratory Building, 2nd Floor (Physics Lab)", "1111-2222-3333", "Monday - Friday, 14:00 - 16:00"),
        # 2. Dra. Maria Elena Rostova
        ("Dra. Maria Elena Rostova, M.Si.", "teacher2@example.com", default_pw, "teacher",
         "Chemistry & Life Sciences", "Laboratory Building, 1st Floor (Chemistry Lab)", "1111-2222-3333", "Monday - Thursday, 13:00 - 15:00"),
        # 3. David Chen, S.Pd.
        ("David Chen, S.Pd.", "teacher3@example.com", default_pw, "teacher",
         "Mathematics & Theatre Arts", "Main Building, 3rd Floor (Faculty Room 302)", "1111-2222-3333", "Daily, 15:30 - 16:30"),
        # 4. Sarah Jenkins, M.Hum.
        ("Sarah Jenkins, M.Hum.", "teacher4@example.com", default_pw, "teacher",
         "English Language & Literature", "Humanities Wing, 1st Floor (Room 110)", "1111-2222-3333", "Monday, Wednesday, Friday, 15:00 - 16:00"),
        # 5. Coach Marcus Vance, S.Pd.
        ("Coach Marcus Vance, S.Pd.", "teacher5@example.com", default_pw, "teacher",
         "Physical Education & Sports", "Gymnasium, 1st Floor (Sports Office)", "1111-2222-3333", "Daily, 14:00 - 17:00"),
        # 6. Alex Rivera, S.Kom.
        ("Alex Rivera, S.Kom.", "teacher6@example.com", default_pw, "teacher",
         "Digital Media & Multimedia Computing", "Innovation Hub, 2nd Floor (Room 204)", "1111-2222-3333", "Tuesday - Thursday, 15:00 - 17:00"),
        # 7. FX. Budi Santoso, M.Si. (Wali Kelas 11-B)
        ("FX. Budi Santoso, M.Si.", "teacher7@example.com", default_pw, "teacher",
         "Applied Chemistry & Student Council Advisor", "Central Faculty Room, 2nd Floor (Desk 14)", "1111-2222-3333", "Monday - Friday, 14:00 - 16:00"),
        # 8. Dra. Theresia Sri Rahayu (Wali Kelas 11-C)
        ("Dra. Theresia Sri Rahayu", "teacher8@example.com", default_pw, "teacher",
         "Applied Biology & Environmental Program", "Central Faculty Room, 2nd Floor (Desk 08)", "1111-2222-3333", "Monday - Thursday, 13:30 - 15:30"),
        # 9. Antonius Hendra Setiawan, S.Pd. (Wali Kelas 11-A)
        ("Antonius Hendra Setiawan, S.Pd.", "teacher9@example.com", default_pw, "teacher",
         "Modern Physics & Robotics Advisor", "Central Faculty Room, 2nd Floor (Desk 22)", "1111-2222-3333", "Daily, 15:00 - 16:30"),
        # 10. Ignatius Wisnu Wardhana, S.Pd.
        ("Ignatius Wisnu Wardhana, S.Pd.", "teacher10@example.com", default_pw, "teacher",
         "Indonesian History & Sociology", "Central Faculty Room, 1st Floor (Desk 03)", "1111-2222-3333", "Monday & Wednesday, 14:30 - 16:00"),
        # 11. Maria Fransisca Dewi, M.Pd.
        ("Maria Fransisca Dewi, M.Pd.", "teacher11@example.com", default_pw, "teacher",
         "Indonesian Language & Literature", "Central Faculty Room, 1st Floor (Desk 05)", "1111-2222-3333", "Tuesday & Thursday, 14:00 - 15:30"),
        # 12. Yulius Eko Prasetyo, S.Kom.
        ("Yulius Eko Prasetyo, S.Kom.", "teacher12@example.com", default_pw, "teacher",
         "Computer Science & AI Programming", "Innovation Hub, 1st Floor (Room 102)", "1111-2222-3333", "Wednesday - Friday, 15:00 - 16:30"),
        # 13. Bernadetta Rini Lestari, S.Pd.
        ("Bernadetta Rini Lestari, S.Pd.", "teacher13@example.com", default_pw, "teacher",
         "Economics & Accounting", "Central Faculty Room, 2nd Floor (Desk 18)", "1111-2222-3333", "Monday - Thursday, 14:00 - 16:00"),
        # 14. Stefanus Bagus Wicaksono, S.Pd.
        ("Stefanus Bagus Wicaksono, S.Pd.", "teacher14@example.com", default_pw, "teacher",
         "Geography & Earth Science", "Central Faculty Room, 1st Floor (Desk 12)", "1111-2222-3333", "Tuesday & Friday, 14:30 - 16:00"),
        # 15. Yohana Agnes Pratiwi, M.Pd.
        ("Yohana Agnes Pratiwi, M.Pd.", "teacher15@example.com", default_pw, "teacher",
         "Visual Arts & Creative Design", "Arts Wing, 1st Floor (Art Studio)", "1111-2222-3333", "Monday - Wednesday, 15:00 - 16:30"),
    ]

    teacher_id_map = {}
    for t in teachers:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, role, department, office_location, contact_phone, office_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7]))
        teacher_id_map[t[1]] = cursor.lastrowid

    # Admin User
    cursor.execute('''
    INSERT INTO users (name, email, password_hash, role)
    VALUES (?, ?, ?, ?)
    ''', ("System Administrator & School Office", "admin@example.com", default_pw, "admin"))

    # 2. Rooms - Facilities & Laboratories
    facilities_data = [
        ("Physics Laboratory", "science_lab", 30, "Science Hall 2nd Floor", teacher_id_map["teacher1@example.com"], "2026", 0, "Advanced physics experimental lab with precision laser tables and mechanics gear.", "flask", json.dumps({"lab_type": "Physics", "safety_guidelines": "Safety goggles required. No food or drinks."})),
        ("Chemistry Laboratory", "science_lab", 32, "Science Hall 1st Floor", teacher_id_map["teacher2@example.com"], "3045", 0, "Fume hoods, Bunsen burners, and titration stations.", "flask", json.dumps({"lab_type": "Chemistry", "safety_guidelines": "Lab coat and goggles mandatory."})),
        ("Biology Laboratory", "science_lab", 28, "Science Hall 1st Floor", teacher_id_map["teacher2@example.com"], "4089", 0, "High-resolution optical microscopes and specimen collections.", "flask", json.dumps({"lab_type": "Biology", "safety_guidelines": "Wash hands before and after sessions."})),
        ("Language Laboratory", "science_lab", 25, "Humanities Wing 102", teacher_id_map["teacher4@example.com"], "1122", 0, "Acoustic audio booths with digital language learning software.", "headphones", json.dumps({"lab_type": "Language", "safety_guidelines": "Use provided alcohol wipes on headsets."})),
        
        ("Auditorium", "event_space", 350, "Main Campus Center", teacher_id_map["teacher3@example.com"], "9900", 0, "Grand stage, surround audio system, and theatrical lighting system.", "theater-masks", json.dumps({"capacity_rules": "Requires AV technician approval for lighting control."})),
        ("Library Conference Room", "event_space", 16, "Central Library 2nd Floor", teacher_id_map["teacher4@example.com"], "7766", 0, "Quiet glass enclosure with conference camera and whiteboard.", "book-reader", json.dumps({})),
        
        ("Podcast Recording Studio", "media_room", 6, "Innovation Hub 201", teacher_id_map["teacher6@example.com"], "8811", 0, "Soundproof recording studio with Shure SM7B mics and Rodecaster Pro.", "podcast", json.dumps({"equipment": ["Rodecaster Pro", "Shure SM7B Mics x4", "Headphone Distribution Amp"]})),
        ("Audiovisual Production Room", "media_room", 12, "Innovation Hub 202", teacher_id_map["teacher6@example.com"], "8822", 0, "4K video editing suite with DaVinci Resolve and green screen booth.", "film", json.dumps({"equipment": ["Green Screen Studio", "4K Video Editing Rig", "Studio Softlights"]})),
        ("Esports & Gaming Room", "media_room", 20, "Student Union 3rd Floor", teacher_id_map["teacher6@example.com"], "8833", 0, "High-performance PC rigs, 240Hz monitors, and team shoutcaster booth.", "gamepad", json.dumps({"equipment": ["240Hz Gaming PCs x10", "Console Gaming Station", "Shoutcaster Desk"]})),
        
        ("Basketball Court (Indoor)", "sports_facility", 40, "Gymnasium Main Hall", teacher_id_map["teacher5@example.com"], "5511", 0, "Hardwood maple court with digital scoreboard.", "basketball-ball", json.dumps({})),
        ("Volleyball Court (Indoor)", "sports_facility", 30, "Gymnasium Court B", teacher_id_map["teacher5@example.com"], "5522", 0, "Regulation net setup with padded posts.", "volleyball-ball", json.dumps({})),
    ]

    for f in facilities_data:
        cursor.execute('''
        INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', f)

    # 3. Classrooms (Class 10-A to Class 12-C, exactly 3 classes per grade level = 9 classes total)
    # Homeroom Mapping:
    # 10-A -> David Chen, 10-B -> Sarah Jenkins, 10-C -> Dr. Thorne
    # 11-A -> Antonius Hendra Setiawan (Walas Darren Austin & Terrius Konstantine)
    # 11-B -> FX. Budi Santoso (Walas Joe Mesiano Hoosan)
    # 11-C -> Dra. Theresia Sri Rahayu (Walas Christiano Rafael Koroh)
    # 12-A -> Coach Marcus Vance, 12-B -> Alex Rivera, 12-C -> Dra. Maria Elena Rostova
    homeroom_assignment_map = {
        "10-A": teacher_id_map["teacher3@example.com"],
        "10-B": teacher_id_map["teacher4@example.com"],
        "10-C": teacher_id_map["teacher1@example.com"],
        "11-A": teacher_id_map["teacher9@example.com"],
        "11-B": teacher_id_map["teacher7@example.com"],
        "11-C": teacher_id_map["teacher8@example.com"],
        "12-A": teacher_id_map["teacher5@example.com"],
        "12-B": teacher_id_map["teacher6@example.com"],
        "12-C": teacher_id_map["teacher2@example.com"]
    }

    room_name_to_id = {}
    grades = ['10', '11', '12']
    sections = ['A', 'B', 'C']

    for g in grades:
        for s in sections:
            class_key = f"{g}-{s}"
            class_name = f"Class {class_key}"
            location = f"Academic Block {g}, Room {s}01"
            tic_id = homeroom_assignment_map.get(class_key, teacher_id_map["teacher1@example.com"])

            cursor.execute('''
            INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
            VALUES (?, 'classroom', 35, ?, ?, '1234', 1, 'Standard academic classroom available for study groups after 15:30.', 'chalkboard-teacher', ?)
            ''', (class_name, location, tic_id, json.dumps({"grade_level": f"Grade {g}", "assigned_homeroom_teacher_id": tic_id})))

            room_id = cursor.lastrowid
            room_name_to_id[class_name] = room_id
            room_name_to_id[class_key] = room_id

            # Update assigned homeroom on the teacher
            if class_key in homeroom_assignment_map:
                assigned_tid = homeroom_assignment_map[class_key]
                cursor.execute("UPDATE users SET assigned_homeroom_classroom_id = ? WHERE id = ?", (room_id, assigned_tid))

    # 4. Students (Using user's exact requested roster, mapped to 11-A, 11-B, 11-C)
    students_data = [
        # Joe Mesiano Hoosan - Class 11-B (Wali Kelas: FX. Budi Santoso)
        ("Joe Mesiano Hoosan", "student1@example.com", default_pw, "252610153", "Grade 11",
         teacher_id_map["teacher7@example.com"], room_name_to_id["Class 11-B"]),

        # Darren Austin Rinaldy - Class 11-A (Wali Kelas: Antonius Hendra Setiawan)
        ("Darren Austin Rinaldy", "student2@example.com", default_pw, "252610112", "Grade 11",
         teacher_id_map["teacher9@example.com"], room_name_to_id["Class 11-A"]),

        # Terrius Konstantine - Class 11-A (Wali Kelas: Antonius Hendra Setiawan)
        ("Terrius Konstantine", "student3@example.com", default_pw, "252610134", "Grade 11",
         teacher_id_map["teacher9@example.com"], room_name_to_id["Class 11-A"]),

        # Christiano Rafael Koroh - Class 11-C (Wali Kelas: Dra. Theresia Sri Rahayu)
        ("Christiano Rafael Koroh", "student4@example.com", default_pw, "252610213", "Grade 11",
         teacher_id_map["teacher8@example.com"], room_name_to_id["Class 11-C"]),
    ]

    for s in students_data:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, role, student_id_number, grade_level, homeroom_teacher_id, homeroom_classroom_id)
        VALUES (?, ?, ?, 'student', ?, ?, ?, ?)
        ''', s)

    conn.commit()
