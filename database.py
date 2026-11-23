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

def seed_demo_data(conn, force=False):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count > 0 and not force:
        # Check if the new demo students already exist
        cursor.execute("SELECT COUNT(*) FROM users WHERE student_id_number = '252610153'")
        if cursor.fetchone()[0] > 0:
            return # Already fully seeded with latest roster

    default_pw = security.generate_password_hash("password123")

    # If force or upgrading: clear bookings, users, rooms safely
    if force or user_count > 0:
        cursor.execute("DELETE FROM bookings")
        cursor.execute("DELETE FROM notifications")
        cursor.execute("DELETE FROM rooms")
        cursor.execute("DELETE FROM users")
        conn.commit()

    # 1. Teachers (15 dedicated teachers with complete contact & room assignment)
    teachers = [
        # 1. Dr. Yohanes Aris Thorne
        ("Dr. Yohanes Aris Thorne, M.Pd.", "thorne@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Fisika & Sains Terapan", "Gedung Laboratorium Lt. 2 (Lab Fisika)", "0812-1111-2021", "Senin - Jumat 14:00 - 16:00"),
        # 2. Dra. Maria Elena Rostova
        ("Dra. Maria Elena Rostova, M.Si.", "rostova@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Kimia & Ilmu Hayati", "Gedung Laboratorium Lt. 1 (Lab Kimia)", "0812-2222-3045", "Senin - Kamis 13:00 - 15:00"),
        # 3. David Chen, S.Pd.
        ("David Chen, S.Pd.", "chen@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Matematika & Seni Teater", "Gedung Utama Lt. 3 (Ruang Guru 302)", "0812-5555-9900", "Setiap Hari 15:30 - 16:30"),
        # 4. Sarah Jenkins, M.Hum.
        ("Sarah Jenkins, M.Hum.", "jenkins@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Bahasa & Sastra Inggris", "Sayap Humaniora Lt. 1 (Ruang 110)", "0812-4444-1122", "Senin, Rabu, Jumat 15:00 - 16:00"),
        # 5. Coach Marcus Vance, S.Pd.
        ("Coach Marcus Vance, S.Pd.", "vance@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Pendidikan Jasmani & Olahraga (PJOK)", "Gedung Gymnasium Lt. 1 (Kantor Olahraga)", "0812-8888-5511", "Setiap Hari 14:00 - 17:00"),
        # 6. Alex Rivera, S.Kom.
        ("Alex Rivera, S.Kom.", "rivera@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Digital Media & Informatika Multimedia", "Innovation Hub Lt. 2 (Ruang 204)", "0812-7777-8888", "Selasa - Kamis 15:00 - 17:00"),
        # 7. FX. Budi Santoso, M.Si. (Wali Kelas 11-B)
        ("FX. Budi Santoso, M.Si.", "budisantoso@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Kimia Terapan & Pembina OSIS", "Ruang Guru Pusat Lt. 2 (Meja 14)", "0813-8821-4402", "Senin - Jumat 14:00 - 16:00"),
        # 8. Dra. Theresia Sri Rahayu (Wali Kelas 11-E)
        ("Dra. Theresia Sri Rahayu", "srirahayu@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Biologi Terapan & Adiwiyata", "Ruang Guru Pusat Lt. 2 (Meja 08)", "0812-9934-5513", "Senin - Kamis 13:30 - 15:30"),
        # 9. Antonius Hendra Setiawan, S.Pd. (Wali Kelas 11-I)
        ("Antonius Hendra Setiawan, S.Pd.", "hendrasetiawan@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Fisika Modern & Pembina Robotika", "Ruang Guru Pusat Lt. 2 (Meja 22)", "0811-7723-9901", "Setiap Hari 15:00 - 16:30"),
        # 10. Ignatius Wisnu Wardhana, S.Pd. (Wali Kelas 11-A)
        ("Ignatius Wisnu Wardhana, S.Pd.", "wisnu@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Sejarah Indonesia & Sosiologi", "Ruang Guru Pusat Lt. 1 (Meja 03)", "0812-3344-5566", "Senin & Rabu 14:30 - 16:00"),
        # 11. Maria Fransisca Dewi, M.Pd. (Wali Kelas 11-C)
        ("Maria Fransisca Dewi, M.Pd.", "dewi@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Bahasa & Sastra Indonesia", "Ruang Guru Pusat Lt. 1 (Meja 05)", "0813-4455-6677", "Selasa & Kamis 14:00 - 15:30"),
        # 12. Yulius Eko Prasetyo, S.Kom. (Wali Kelas 11-D)
        ("Yulius Eko Prasetyo, S.Kom.", "ekoprasetyo@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Informatika & Coding AI", "Innovation Hub Lt. 1 (Ruang 102)", "0812-5566-7788", "Rabu - Jumat 15:00 - 16:30"),
        # 13. Bernadetta Rini Lestari, S.Pd. (Wali Kelas 11-F)
        ("Bernadetta Rini Lestari, S.Pd.", "rinilestari@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Ekonomi & Akuntansi", "Ruang Guru Pusat Lt. 2 (Meja 18)", "0813-6677-8899", "Senin - Kamis 14:00 - 16:00"),
        # 14. Stefanus Bagus Wicaksono, S.Pd. (Wali Kelas 11-G)
        ("Stefanus Bagus Wicaksono, S.Pd.", "baguswicaksono@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Geografi & Kebumian", "Ruang Guru Pusat Lt. 1 (Meja 12)", "0812-7788-9900", "Selasa & Jumat 14:30 - 16:00"),
        # 15. Yohana Agnes Pratiwi, M.Pd. (Wali Kelas 11-H)
        ("Yohana Agnes Pratiwi, M.Pd.", "agnespratiwi@smamarsudirinibekasi.sch.id", default_pw, "teacher",
         "Seni Rupa & Desain Kreatif", "Sayap Seni Lt. 1 (Studio Seni)", "0813-8899-0011", "Senin - Rabu 15:00 - 16:30"),
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
    ''', ("System Administrator & Tata Usaha", "admin@smamarsudirinibekasi.sch.id", default_pw, "admin"))

    # 2. Rooms - Facilities & Laboratories
    facilities_data = [
        ("Physics Laboratory", "science_lab", 30, "Science Hall 2nd Floor", teacher_id_map["thorne@smamarsudirinibekasi.sch.id"], "2026", 0, "Advanced physics experimental lab with precision laser tables and mechanics gear.", "flask", json.dumps({"lab_type": "Physics", "safety_guidelines": "Safety goggles required. No food or drinks."})),
        ("Chemistry Laboratory", "science_lab", 32, "Science Hall 1st Floor", teacher_id_map["rostova@smamarsudirinibekasi.sch.id"], "3045", 0, "Fume hoods, Bunsen burners, and titration stations.", "flask", json.dumps({"lab_type": "Chemistry", "safety_guidelines": "Lab coat and goggles mandatory."})),
        ("Biology Laboratory", "science_lab", 28, "Science Hall 1st Floor", teacher_id_map["rostova@smamarsudirinibekasi.sch.id"], "4089", 0, "High-resolution optical microscopes and specimen collections.", "flask", json.dumps({"lab_type": "Biology", "safety_guidelines": "Wash hands before and after sessions."})),
        ("Language Laboratory", "science_lab", 25, "Humanities Wing 102", teacher_id_map["jenkins@smamarsudirinibekasi.sch.id"], "1122", 0, "Acoustic audio booths with digital language learning software.", "headphones", json.dumps({"lab_type": "Language", "safety_guidelines": "Use provided alcohol wipes on headsets."})),
        
        ("Auditorium", "event_space", 350, "Main Campus Center", teacher_id_map["chen@smamarsudirinibekasi.sch.id"], "9900", 0, "Grand stage, surround audio system, and theatrical lighting system.", "theater-masks", json.dumps({"capacity_rules": "Requires AV technician approval for lighting control."})),
        ("Library Conference Room", "event_space", 16, "Central Library 2nd Floor", teacher_id_map["jenkins@smamarsudirinibekasi.sch.id"], "7766", 0, "Quiet glass enclosure with conference camera and whiteboard.", "book-reader", json.dumps({})),
        
        ("Podcast Recording Studio", "media_room", 6, "Innovation Hub 201", teacher_id_map["rivera@smamarsudirinibekasi.sch.id"], "8811", 0, "Soundproof recording studio with Shure SM7B mics and Rodecaster Pro.", "podcast", json.dumps({"equipment": ["Rodecaster Pro", "Shure SM7B Mics x4", "Headphone Distribution Amp"]})),
        ("Audiovisual Production Room", "media_room", 12, "Innovation Hub 202", teacher_id_map["rivera@smamarsudirinibekasi.sch.id"], "8822", 0, "4K video editing suite with DaVinci Resolve and green screen booth.", "film", json.dumps({"equipment": ["Green Screen Studio", "4K Video Editing Rig", "Studio Softlights"]})),
        ("Esports & Gaming Room", "media_room", 20, "Student Union 3rd Floor", teacher_id_map["rivera@smamarsudirinibekasi.sch.id"], "8833", 0, "High-performance PC rigs, 240Hz monitors, and team shoutcaster booth.", "gamepad", json.dumps({"equipment": ["240Hz Gaming PCs x10", "Console Gaming Station", "Shoutcaster Desk"]})),
        
        ("Basketball Court (Indoor)", "sports_facility", 40, "Gymnasium Main Hall", teacher_id_map["vance@smamarsudirinibekasi.sch.id"], "5511", 0, "Hardwood maple court with digital scoreboard.", "basketball-ball", json.dumps({})),
        ("Volleyball Court (Indoor)", "sports_facility", 30, "Gymnasium Court B", teacher_id_map["vance@smamarsudirinibekasi.sch.id"], "5522", 0, "Regulation net setup with padded posts.", "volleyball-ball", json.dumps({})),
    ]

    for f in facilities_data:
        cursor.execute('''
        INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', f)

    # 3. Classrooms (Class 10-A to Class 12-I, total 27 classes)
    # Homeroom Mapping:
    # 10-A -> David Chen, 10-B -> Sarah Jenkins, 10-C -> Dr. Thorne, 10-D -> Dra. Elena
    # 11-A -> Wisnu Wardhana, 11-B -> FX. Budi Santoso, 11-C -> Dewi, 11-D -> Eko Prasetyo
    # 11-E -> Dra. Theresia Sri Rahayu, 11-F -> Rini Lestari, 11-G -> Bagus Wicaksono
    # 11-H -> Agnes Pratiwi, 11-I -> Antonius Hendra Setiawan
    # 12-A -> Coach Vance, 12-B -> Alex Rivera
    homeroom_assignment_map = {
        "10-A": teacher_id_map["chen@smamarsudirinibekasi.sch.id"],
        "10-B": teacher_id_map["jenkins@smamarsudirinibekasi.sch.id"],
        "10-C": teacher_id_map["thorne@smamarsudirinibekasi.sch.id"],
        "10-D": teacher_id_map["rostova@smamarsudirinibekasi.sch.id"],
        "11-A": teacher_id_map["wisnu@smamarsudirinibekasi.sch.id"],
        "11-B": teacher_id_map["budisantoso@smamarsudirinibekasi.sch.id"], # Walas for Joe Mesiano Hoosan
        "11-C": teacher_id_map["dewi@smamarsudirinibekasi.sch.id"],
        "11-D": teacher_id_map["ekoprasetyo@smamarsudirinibekasi.sch.id"],
        "11-E": teacher_id_map["srirahayu@smamarsudirinibekasi.sch.id"],   # Walas for Christiano Rafael Koroh
        "11-F": teacher_id_map["rinilestari@smamarsudirinibekasi.sch.id"],
        "11-G": teacher_id_map["baguswicaksono@smamarsudirinibekasi.sch.id"],
        "11-H": teacher_id_map["agnespratiwi@smamarsudirinibekasi.sch.id"],
        "11-I": teacher_id_map["hendrasetiawan@smamarsudirinibekasi.sch.id"], # Walas for Darren Austin & Terrius Konstantine
        "12-A": teacher_id_map["vance@smamarsudirinibekasi.sch.id"],
        "12-B": teacher_id_map["rivera@smamarsudirinibekasi.sch.id"]
    }

    room_name_to_id = {}
    grades = ['10', '11', '12']
    sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']

    for g in grades:
        for s in sections:
            class_key = f"{g}-{s}"
            class_name = f"Class {class_key}"
            location = f"Academic Block {g}, Room {s}01"
            tic_id = homeroom_assignment_map.get(class_key, teacher_id_map["thorne@smamarsudirinibekasi.sch.id"])

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

    # 4. Students (Using user's exact requested roster)
    students_data = [
        # Joe Mesiano Hoosan - Class 11-B (Wali Kelas: FX. Budi Santoso)
        ("Joe Mesiano Hoosan", "252610153@smamarsudirinibekasi.sch.id", default_pw, "252610153", "Grade 11",
         teacher_id_map["budisantoso@smamarsudirinibekasi.sch.id"], room_name_to_id["Class 11-B"]),

        # Darren Austin Rinaldy - Class 11-I (Wali Kelas: Antonius Hendra Setiawan)
        ("Darren Austin Rinaldy", "252610112@smamarsudirinibekasi.sch.id", default_pw, "252610112", "Grade 11",
         teacher_id_map["hendrasetiawan@smamarsudirinibekasi.sch.id"], room_name_to_id["Class 11-I"]),

        # Terrius Konstantine - Class 11-I (Wali Kelas: Antonius Hendra Setiawan)
        ("Terrius Konstantine", "252610134@smamarsudirinibekasi.sch.id", default_pw, "252610134", "Grade 11",
         teacher_id_map["hendrasetiawan@smamarsudirinibekasi.sch.id"], room_name_to_id["Class 11-I"]),

        # Christiano Rafael Koroh - Class 11-E (Wali Kelas: Dra. Theresia Sri Rahayu)
        ("Christiano Rafael Koroh", "252610213@smamarsudirinibekasi.sch.id", default_pw, "252610213", "Grade 11",
         teacher_id_map["srirahayu@smamarsudirinibekasi.sch.id"], room_name_to_id["Class 11-E"]),
    ]

    for s in students_data:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, role, student_id_number, grade_level, homeroom_teacher_id, homeroom_classroom_id)
        VALUES (?, ?, ?, 'student', ?, ?, ?, ?)
        ''', s)

    conn.commit()
