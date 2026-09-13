from database import get_db
from models import User, Student, Teacher, Admin

class AuthService:
    @staticmethod
    def authenticate(email, password):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None, "Invalid school email or password."

        user_obj = AuthService._instantiate_user(row)
        if not user_obj.check_password(password):
            return None, "Invalid school email or password."

        return user_obj, None

    @staticmethod
    def get_user_by_id(user_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return AuthService._instantiate_user(row)

    @staticmethod
    def get_student_by_number(student_id_number):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE UPPER(student_id_number) = UPPER(?) AND role = 'student'", (student_id_number.strip(),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return AuthService._instantiate_user(row)

    @staticmethod
    def _instantiate_user(row):
        role = row['role']
        if role == 'student':
            return Student(
                id=row['id'], name=row['name'], email=row['email'],
                student_id_number=row['student_id_number'], grade_level=row['grade_level'],
                homeroom_teacher_id=row['homeroom_teacher_id'], homeroom_classroom_id=row['homeroom_classroom_id'],
                password_hash=row['password_hash']
            )
        elif role == 'teacher':
            return Teacher(
                id=row['id'], name=row['name'], email=row['email'],
                department=row['department'], office_location=row['office_location'],
                contact_phone=row['contact_phone'], office_hours=row['office_hours'],
                assigned_homeroom_classroom_id=row['assigned_homeroom_classroom_id'],
                password_hash=row['password_hash']
            )
        elif role == 'admin':
            return Admin(
                id=row['id'], name=row['name'], email=row['email'], password_hash=row['password_hash']
            )
        return User(id=row['id'], name=row['name'], email=row['email'], role=role, password_hash=row['password_hash'])
