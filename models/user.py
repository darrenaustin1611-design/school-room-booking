import werkzeug.security as security

class User:
    def __init__(self, id, name, email, role, password_hash=None):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.password_hash = password_hash

    def set_password(self, password):
        self.password_hash = security.generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return security.check_password_hash(self.password_hash, password)

    def is_student(self):
        return self.role == 'student'

    def is_teacher(self):
        return self.role == 'teacher'

    def is_admin(self):
        return self.role == 'admin'

    def get_role_display(self):
        """Polymorphic method: returns human-readable role display string."""
        return self.role.title()

    def get_home_route(self):
        """Polymorphic method: returns the designated landing route name."""
        return 'dashboard'

    def can_approve_booking(self, booking):
        """Polymorphic method: determines if this user role can approve a booking."""
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'role_display': self.get_role_display()
        }


class Student(User):
    def __init__(self, id, name, email, student_id_number, grade_level, homeroom_teacher_id=None, homeroom_classroom_id=None, password_hash=None):
        super().__init__(id, name, email, role='student', password_hash=password_hash)
        self.student_id_number = student_id_number
        self.grade_level = grade_level
        self.homeroom_teacher_id = homeroom_teacher_id
        self.homeroom_classroom_id = homeroom_classroom_id

    def get_role_display(self):
        # Polymorphic override for Student
        return f"Siswa ({self.grade_level})"

    def get_home_route(self):
        # Polymorphic override for Student landing page
        return 'dashboard'

    def can_approve_booking(self, booking):
        # Students cannot approve bookings
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'student_id_number': self.student_id_number,
            'grade_level': self.grade_level,
            'homeroom_teacher_id': self.homeroom_teacher_id,
            'homeroom_classroom_id': self.homeroom_classroom_id
        })
        return data


class Teacher(User):
    def __init__(self, id, name, email, department, office_location, contact_phone, office_hours, assigned_homeroom_classroom_id=None, password_hash=None):
        super().__init__(id, name, email, role='teacher', password_hash=password_hash)
        self.department = department
        self.office_location = office_location
        self.contact_phone = contact_phone
        self.office_hours = office_hours
        self.assigned_homeroom_classroom_id = assigned_homeroom_classroom_id

    def is_homeroom_teacher(self):
        return self.assigned_homeroom_classroom_id is not None

    def get_role_display(self):
        # Polymorphic override for Teacher
        if self.is_homeroom_teacher():
            return f"Wali Kelas ({self.department})"
        return f"Guru Mata Pelajaran ({self.department})"

    def get_home_route(self):
        # Polymorphic override for Teacher landing page
        return 'dashboard'

    def can_approve_booking(self, booking):
        # Polymorphic override: TIC can approve bookings for their assigned facility
        if not booking:
            return False
        return booking.teacher_in_charge_id == self.id

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'department': self.department,
            'office_location': self.office_location,
            'contact_phone': self.contact_phone,
            'office_hours': self.office_hours,
            'assigned_homeroom_classroom_id': self.assigned_homeroom_classroom_id,
            'is_homeroom_teacher': self.is_homeroom_teacher()
        })
        return data


class Admin(User):
    def __init__(self, id, name, email, password_hash=None):
        super().__init__(id, name, email, role='admin', password_hash=password_hash)

    def get_role_display(self):
        # Polymorphic override for Admin
        return "Administrator Sistem & Tata Usaha"

    def get_home_route(self):
        # Polymorphic override: Admin lands directly on the Data Center
        return 'admin_data_center'

    def can_approve_booking(self, booking):
        # Polymorphic override: Admin has universal approval authority
        return True
