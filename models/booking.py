import json
from datetime import datetime

class BookingStatus:
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    CHECKED_IN = 'CHECKED_IN'
    PENDING_CONFIRMATION = 'PENDING_CONFIRMATION' # Sent "Are you coming?" prompt
    EXPIRED = 'EXPIRED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class Booking:
    def __init__(self, id, primary_student_id, room_id, booking_date, start_time, end_time, 
                 purpose, teacher_in_charge_id, homeroom_teacher_id, co_booker_ids=None,
                 status=BookingStatus.PENDING, checked_in_at=None, checked_in_by_student_id=None, 
                 checked_out_at=None, grace_period_extended=False, prompt_sent_at=None,
                 extension_status='NONE', extension_minutes=0, created_at=None):
        self.id = id
        self.primary_student_id = primary_student_id
        self.co_booker_ids = co_booker_ids if co_booker_ids is not None else []
        if isinstance(self.co_booker_ids, str):
            try:
                self.co_booker_ids = json.loads(self.co_booker_ids)
            except Exception:
                self.co_booker_ids = []
        self.room_id = room_id
        self.booking_date = booking_date # YYYY-MM-DD
        self.start_time = start_time     # HH:MM
        self.end_time = end_time         # HH:MM
        self.purpose = purpose
        self.teacher_in_charge_id = teacher_in_charge_id
        self.homeroom_teacher_id = homeroom_teacher_id
        self.status = status
        self.checked_in_at = checked_in_at
        self.checked_in_by_student_id = checked_in_by_student_id
        self.checked_out_at = checked_out_at
        self.grace_period_extended = bool(grace_period_extended)
        self.prompt_sent_at = prompt_sent_at
        self.extension_status = extension_status # NONE, PENDING, APPROVED, REJECTED
        self.extension_minutes = extension_minutes
        self.created_at = created_at or datetime.now().isoformat()

    def is_active(self):
        """Active bookings count towards the 1 active booking per student rule."""
        return self.status in [BookingStatus.PENDING, BookingStatus.APPROVED, BookingStatus.CHECKED_IN, BookingStatus.PENDING_CONFIRMATION]

    def is_authorized_student(self, student_id, student_number=None):
        """Checks if a student is either the primary booker or a listed co-booker."""
        if str(self.primary_student_id) == str(student_id):
            return True
        if student_number and student_number in self.co_booker_ids:
            return True
        if str(student_id) in [str(x) for x in self.co_booker_ids]:
            return True
        return False

    def get_allowed_grace_minutes(self):
        return 30 if self.grace_period_extended else 15

    def to_dict(self):
        return {
            'id': self.id,
            'primary_student_id': self.primary_student_id,
            'co_booker_ids': self.co_booker_ids,
            'room_id': self.room_id,
            'booking_date': self.booking_date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'purpose': self.purpose,
            'teacher_in_charge_id': self.teacher_in_charge_id,
            'homeroom_teacher_id': self.homeroom_teacher_id,
            'status': self.status,
            'checked_in_at': self.checked_in_at,
            'checked_in_by_student_id': self.checked_in_by_student_id,
            'checked_out_at': self.checked_out_at,
            'grace_period_extended': self.grace_period_extended,
            'prompt_sent_at': self.prompt_sent_at,
            'extension_status': self.extension_status,
            'extension_minutes': self.extension_minutes,
            'created_at': self.created_at
        }
