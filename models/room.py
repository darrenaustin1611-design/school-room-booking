from datetime import datetime

class Room:
    def __init__(self, id, name, category, capacity, location, teacher_in_charge_id, qr_pin="1234", requires_after_hours_only=False, description="", icon="building"):
        self.id = id
        self.name = name
        self.category = category # science_lab, media_room, sports_facility, classroom, event_space
        self.capacity = capacity
        self.location = location
        self.teacher_in_charge_id = teacher_in_charge_id
        self.qr_pin = qr_pin
        self.requires_after_hours_only = requires_after_hours_only
        self.description = description
        self.icon = icon

    def get_effective_tic_id(self, student=None):
        """Polymorphic method: returns the teacher ID responsible for approving bookings."""
        return self.teacher_in_charge_id

    def verify_qr_pin(self, pin):
        return str(self.qr_pin).strip() == str(pin).strip()

    def check_time_restriction(self, start_time_str):
        """Polymorphic method: validates time constraints before booking."""
        if not self.requires_after_hours_only:
            return True, None
        
        try:
            time_obj = datetime.strptime(start_time_str, "%H:%M").time()
            after_hours_cutoff = datetime.strptime("15:30", "%H:%M").time()
            if time_obj < after_hours_cutoff:
                return False, "Classrooms can only be booked after school hours (after 15:30)."
        except ValueError:
            pass
        return True, None

    def get_special_guidelines(self):
        """Polymorphic method: returns room-specific usage rules and safety guidelines."""
        return "Patuhi ketertiban umum dan jaga kebersihan fasilitas selama sesi penggunaan."

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'capacity': self.capacity,
            'location': self.location,
            'teacher_in_charge_id': self.teacher_in_charge_id,
            'qr_pin': self.qr_pin,
            'requires_after_hours_only': self.requires_after_hours_only,
            'description': self.description,
            'icon': self.icon,
            'special_guidelines': self.get_special_guidelines()
        }


class ScienceLab(Room):
    def __init__(self, id, name, capacity, location, teacher_in_charge_id, lab_type, safety_guidelines, qr_pin="1234", description=""):
        super().__init__(id, name, category="science_lab", capacity=capacity, location=location, 
                         teacher_in_charge_id=teacher_in_charge_id, qr_pin=qr_pin, 
                         requires_after_hours_only=False, description=description, icon="flask")
        self.lab_type = lab_type # Physics, Chemistry, Biology, Language
        self.safety_guidelines = safety_guidelines

    def get_special_guidelines(self):
        # Polymorphic override for Science Laboratories
        return f"Panduan Keselamatan Lab {self.lab_type}: {self.safety_guidelines} Wajib menggunakan jas lab dan kacamata pengaman jika diperlukan."

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'lab_type': self.lab_type,
            'safety_guidelines': self.safety_guidelines
        })
        return data


class MediaRoom(Room):
    def __init__(self, id, name, capacity, location, teacher_in_charge_id, equipment_list, qr_pin="1234", description=""):
        super().__init__(id, name, category="media_room", capacity=capacity, location=location,
                         teacher_in_charge_id=teacher_in_charge_id, qr_pin=qr_pin,
                         requires_after_hours_only=False, description=description, icon="video")
        self.equipment_list = equipment_list

    def get_special_guidelines(self):
        # Polymorphic override for Media & Production Rooms
        eq_str = ", ".join(self.equipment_list) if isinstance(self.equipment_list, list) else str(self.equipment_list)
        return f"Peralatan Khusus: {eq_str}. Harap matikan seluruh perangkat audio/video dan pendingin ruangan setelah selesai."

    def to_dict(self):
        data = super().to_dict()
        data.update({'equipment_list': self.equipment_list})
        return data


class SportsFacility(Room):
    def __init__(self, id, name, capacity, location, teacher_in_charge_id, court_type, qr_pin="1234", description=""):
        super().__init__(id, name, category="sports_facility", capacity=capacity, location=location,
                         teacher_in_charge_id=teacher_in_charge_id, qr_pin=qr_pin,
                         requires_after_hours_only=False, description=description, icon="trophy")
        self.court_type = court_type

    def get_special_guidelines(self):
        # Polymorphic override for Sports Facilities
        return f"Area Olahraga ({self.court_type}): Wajib mengenakan pakaian & sepatu olahraga standar. Dilarang membawa makanan ke dalam lapangan."

    def to_dict(self):
        data = super().to_dict()
        data.update({'court_type': self.court_type})
        return data


class Classroom(Room):
    def __init__(self, id, name, capacity, location, assigned_homeroom_teacher_id, grade_level, qr_pin="1234", description=""):
        # For a classroom, the teacher in charge IS the assigned homeroom teacher!
        super().__init__(id, name, category="classroom", capacity=capacity, location=location,
                         teacher_in_charge_id=assigned_homeroom_teacher_id, qr_pin=qr_pin,
                         requires_after_hours_only=True, description=description, icon="chalkboard-teacher")
        self.assigned_homeroom_teacher_id = assigned_homeroom_teacher_id
        self.grade_level = grade_level

    def get_effective_tic_id(self, student=None):
        # Polymorphic override: For a classroom, approval is routed to its assigned Homeroom Teacher
        return self.assigned_homeroom_teacher_id

    def check_time_restriction(self, start_time_str):
        # Polymorphic override: Enforce classroom after-hours rule (after 15:30)
        try:
            time_obj = datetime.strptime(start_time_str, "%H:%M").time()
            after_hours_cutoff = datetime.strptime("15:30", "%H:%M").time()
            if time_obj < after_hours_cutoff:
                return False, "Classrooms can only be booked after school hours (Ruang kelas hanya dapat dipinjam setelah pukul 15:30)."
        except ValueError:
            pass
        return True, None

    def get_special_guidelines(self):
        # Polymorphic override for Standard Classrooms
        return f"Ruang Belajar {self.grade_level}: Hanya dapat dipinjam untuk kegiatan belajar kelompok setelah pukul 15:30 dengan persetujuan Wali Kelas."

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'assigned_homeroom_teacher_id': self.assigned_homeroom_teacher_id,
            'grade_level': self.grade_level
        })
        return data
