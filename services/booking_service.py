import json
from datetime import datetime, timedelta
from database import get_db
from models import Booking, BookingStatus, Notification
from services.room_service import RoomService
from services.auth_service import AuthService
from config import Config

class BookingService:
    
    @staticmethod
    def create_booking(primary_student_id, room_id, booking_date, start_time, end_time, purpose, co_booker_student_numbers=None):
        conn = get_db()
        cursor = conn.cursor()

        student = AuthService.get_user_by_id(primary_student_id)
        if not student or not student.is_student():
            conn.close()
            return None, "Invalid primary student user."

        room = RoomService.get_room_by_id(room_id)
        if not room:
            conn.close()
            return None, "Selected facility or room does not exist."

        # 1. Enforce After-Hours rule for Classrooms
        allowed, msg = room.check_time_restriction(start_time)
        if not allowed:
            conn.close()
            return None, msg

        # 2. Validate Duration (Max 2 hours)
        try:
            fmt = "%H:%M"
            t1 = datetime.strptime(start_time, fmt)
            t2 = datetime.strptime(end_time, fmt)
            duration_minutes = (t2 - t1).total_seconds() / 60
            if duration_minutes <= 0:
                conn.close()
                return None, "End time must be after start time."
            if duration_minutes > Config.MAX_BOOKING_HOURS * 60:
                conn.close()
                return None, f"Booking duration cannot exceed {Config.MAX_BOOKING_HOURS} hours."
        except ValueError:
            conn.close()
            return None, "Invalid time format. Use HH:MM."

        # 3. Check if primary student holds an active booking (1 active booking limit)
        active_statuses = "('PENDING', 'APPROVED', 'CHECKED_IN', 'PENDING_CONFIRMATION')"
        
        cursor.execute(f"SELECT id FROM bookings WHERE primary_student_id = ? AND status IN {active_statuses}", (primary_student_id,))
        if cursor.fetchone():
            conn.close()
            return None, "You already have an active booking. Students can only hold 1 active booking at a time."

        # 4. Check Room Schedule Overlap
        cursor.execute(f"""
            SELECT id, start_time, end_time FROM bookings 
            WHERE room_id = ? AND booking_date = ? AND status IN {active_statuses}
        """, (room_id, booking_date))
        
        existing_bookings = cursor.fetchall()
        req_start = datetime.strptime(f"{booking_date} {start_time}", "%Y-%m-%d %H:%M")
        req_end = datetime.strptime(f"{booking_date} {end_time}", "%Y-%m-%d %H:%M")

        for eb in existing_bookings:
            e_start = datetime.strptime(f"{booking_date} {eb['start_time']}", "%Y-%m-%d %H:%M")
            e_end = datetime.strptime(f"{booking_date} {eb['end_time']}", "%Y-%m-%d %H:%M")
            # Overlap check
            if max(req_start, e_start) < min(req_end, e_end):
                conn.close()
                return None, f"Room '{room.name}' is already booked during {eb['start_time']} - {eb['end_time']} on {booking_date}."

        # 5. Resolve Approval Routing
        tic_id = room.get_effective_tic_id(student)
        homeroom_teacher_id = student.homeroom_teacher_id or tic_id
        now_str = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO bookings (primary_student_id, co_booker_ids, room_id, booking_date, start_time, end_time,
                                  purpose, teacher_in_charge_id, homeroom_teacher_id, status, created_at)
            VALUES (?, '[]', ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (primary_student_id, room_id, booking_date, start_time, end_time, purpose, tic_id, homeroom_teacher_id, now_str))

        booking_id = cursor.lastrowid

        # 7. Create Notifications
        # A) Request to Teacher in Charge
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
            VALUES (?, ?, ?, 'APPROVAL_REQUEST', ?, ?)
        """, (tic_id, "New Booking Approval Needed", 
              f"Student {student.name} requested to book '{room.name}' on {booking_date} ({start_time}-{end_time}).", booking_id, now_str))

        # B) FYI to Homeroom Teacher (if different from TIC)
        if homeroom_teacher_id and homeroom_teacher_id != tic_id:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
                VALUES (?, ?, ?, 'FYI_NOTIFICATION', ?, ?)
            """, (homeroom_teacher_id, "FYI: Homeroom Student Booking", 
                  f"Your homeroom student {student.name} requested room '{room.name}' on {booking_date}.", booking_id, now_str))

        conn.commit()
        conn.close()

        return BookingService.get_booking_by_id(booking_id), None

    @staticmethod
    def get_booking_by_id(booking_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return BookingService._instantiate_booking(row)

    @staticmethod
    def get_user_bookings(user_id):
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return []
        
        conn = get_db()
        cursor = conn.cursor()
        
        if user.is_student():
            # Get bookings where student is primary OR listed as co-booker
            cursor.execute("SELECT * FROM bookings ORDER BY id DESC")
            all_rows = cursor.fetchall()
            user_bookings = []
            for r in all_rows:
                b = BookingService._instantiate_booking(r)
                if b.is_authorized_student(user.id, user.student_id_number):
                    user_bookings.append(b)
            conn.close()
            return user_bookings
        
        elif user.is_teacher():
            cursor.execute("SELECT * FROM bookings WHERE teacher_in_charge_id = ? OR homeroom_teacher_id = ? ORDER BY id DESC", (user.id, user.id))
            rows = cursor.fetchall()
            conn.close()
            return [BookingService._instantiate_booking(r) for r in rows]

        elif user.is_admin():
            cursor.execute("SELECT * FROM bookings ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()
            return [BookingService._instantiate_booking(r) for r in rows]
            
        conn.close()
        return []

    @staticmethod
    def approve_booking(booking_id, teacher_id):
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking:
            return False, "Booking not found."
        
        if booking.teacher_in_charge_id != teacher_id:
            return False, "Unauthorized. Only the assigned Teacher-in-Charge can approve this room request."

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status = 'APPROVED' WHERE id = ?", (booking_id,))
        
        now_str = datetime.now().isoformat()
        room = RoomService.get_room_by_id(booking.room_id)
        room_name = room.name if room else "Room"

        # Notify Primary Student
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
            VALUES (?, 'Booking Approved!', ?, 'STATUS_UPDATE', ?, ?)
        """, (booking.primary_student_id, f"Your request for '{room_name}' on {booking.booking_date} has been APPROVED.", booking_id, now_str))

        conn.commit()
        conn.close()
        return True, "Booking approved successfully!"

    @staticmethod
    def reject_booking(booking_id, teacher_id, reason="No reason provided"):
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking:
            return False, "Booking not found."

        if booking.teacher_in_charge_id != teacher_id:
            return False, "Unauthorized."

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status = 'REJECTED' WHERE id = ?", (booking_id,))
        
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
            VALUES (?, 'Booking Declined', ?, 'STATUS_UPDATE', ?, ?)
        """, (booking.primary_student_id, f"Your booking request was declined. Reason: {reason}", booking_id, now_str))

        conn.commit()
        conn.close()
        return True, "Booking request declined."

    @staticmethod
    def check_in(booking_id, user_id, pin_input=None):
        """Mulai Pakai: simple confirmation for primary student or admin without QR/PIN."""
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking:
            return False, "Pemesanan tidak ditemukan."

        user = AuthService.get_user_by_id(user_id)
        if not user:
            return False, "Pengguna tidak valid."

        is_authorized = (user.id == booking.primary_student_id) or user.is_admin()
        if not is_authorized:
            return False, "Anda tidak memiliki wewenang untuk memulai pemakaian ruangan ini."

        if booking.status not in [BookingStatus.APPROVED, BookingStatus.PENDING_CONFIRMATION]:
            return False, f"Tidak dapat memulai pemakaian. Status pemesanan: {booking.status}."

        room = RoomService.get_room_by_id(booking.room_id)
        room_name = room.name if room else "Ruangan"

        now_str = datetime.now().isoformat()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bookings SET status = 'CHECKED_IN', checked_in_at = ?, checked_in_by_student_id = ?
            WHERE id = ?
        """, (now_str, user_id, booking_id))
        conn.commit()
        conn.close()

        return True, f"Ruangan {room_name} berhasil mulai digunakan!"

    @staticmethod
    def check_out(booking_id, user_id):
        """Selesai Pakai: simple confirmation for primary student or admin."""
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking:
            return False, "Pemesanan tidak ditemukan."

        user = AuthService.get_user_by_id(user_id)
        if not user:
            return False, "Pengguna tidak valid."

        is_authorized = (user.id == booking.primary_student_id) or user.is_admin()
        if not is_authorized:
            return False, "Anda tidak memiliki wewenang untuk menyelesaikan pemakaian ruangan ini."

        if booking.status != BookingStatus.CHECKED_IN:
            return False, "Pemesanan belum atau tidak sedang digunakan."

        now_str = datetime.now().isoformat()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bookings SET status = 'COMPLETED', checked_out_at = ? WHERE id = ?
        """, (now_str, booking_id))
        conn.commit()
        conn.close()

        return True, "Pemakaian ruangan telah selesai. Terima kasih!"

    @staticmethod
    def confirm_coming(booking_id, student_id):
        """Student clicks 'Yes, I'm coming' on the 15-min warning prompt -> extends grace by +15 mins (total 30)."""
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking:
            return False, "Booking not found."

        student = AuthService.get_user_by_id(student_id)
        if not booking.is_authorized_student(student_id, getattr(student, 'student_id_number', None)):
            return False, "Unauthorized."

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bookings SET grace_period_extended = 1, status = 'APPROVED' WHERE id = ?
        """, (booking_id,))
        conn.commit()
        conn.close()

        return True, "Grace period extended by +15 minutes! Please scan the QR code upon arrival within 30 minutes of start time."

    @staticmethod
    def request_extension(booking_id, student_id, extra_minutes):
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking or booking.status != BookingStatus.CHECKED_IN:
            return False, "Must be checked in to request a time extension."

        student = AuthService.get_user_by_id(student_id)
        if not booking.is_authorized_student(student_id, getattr(student, 'student_id_number', None)):
            return False, "Unauthorized."

        # Check if extended end time conflicts with another booking
        current_end_dt = datetime.strptime(f"{booking.booking_date} {booking.end_time}", "%Y-%m-%d %H:%M")
        new_end_dt = current_end_dt + timedelta(minutes=int(extra_minutes))
        new_end_str = new_end_dt.strftime("%H:%M")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE room_id = ? AND booking_date = ? AND id != ? 
            AND status IN ('PENDING', 'APPROVED', 'CHECKED_IN')
            AND start_time < ? AND end_time > ?
        """, (booking.room_id, booking.booking_date, booking_id, new_end_str, booking.end_time))

        if cursor.fetchone():
            conn.close()
            return False, "Extension unavailable: another student has booked the room for the subsequent slot."

        cursor.execute("""
            UPDATE bookings SET extension_status = 'PENDING', extension_minutes = ? WHERE id = ?
        """, (extra_minutes, booking_id))

        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
            VALUES (?, 'Extension Request', ?, 'APPROVAL_REQUEST', ?, ?)
        """, (booking.teacher_in_charge_id, f"Student requested +{extra_minutes} mins extension for booking #{booking_id}.", booking_id, now_str))

        conn.commit()
        conn.close()
        return True, f"Extension request (+{extra_minutes} mins) sent to Teacher-in-Charge!"

    @staticmethod
    def approve_extension(booking_id, teacher_id):
        booking = BookingService.get_booking_by_id(booking_id)
        if not booking or booking.teacher_in_charge_id != teacher_id:
            return False, "Unauthorized."

        current_end_dt = datetime.strptime(f"{booking.booking_date} {booking.end_time}", "%Y-%m-%d %H:%M")
        new_end_dt = current_end_dt + timedelta(minutes=booking.extension_minutes)
        new_end_str = new_end_dt.strftime("%H:%M")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bookings SET end_time = ?, extension_status = 'APPROVED' WHERE id = ?
        """, (new_end_str, booking_id))
        
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
            VALUES (?, 'Extension Approved!', ?, 'STATUS_UPDATE', ?, ?)
        """, (booking.primary_student_id, f"Your extension for +{booking.extension_minutes} mins was approved. New end time: {new_end_str}", booking_id, now_str))

        conn.commit()
        conn.close()
        return True, f"Approved! Booking extended to {new_end_str}."

    @staticmethod
    def _instantiate_booking(row):
        return Booking(
            id=row['id'], primary_student_id=row['primary_student_id'],
            co_booker_ids=row['co_booker_ids'], room_id=row['room_id'],
            booking_date=row['booking_date'], start_time=row['start_time'], end_time=row['end_time'],
            purpose=row['purpose'], teacher_in_charge_id=row['teacher_in_charge_id'],
            homeroom_teacher_id=row['homeroom_teacher_id'], status=row['status'],
            checked_in_at=row['checked_in_at'], checked_in_by_student_id=row['checked_in_by_student_id'],
            checked_out_at=row['checked_out_at'], grace_period_extended=bool(row['grace_period_extended']),
            prompt_sent_at=row['prompt_sent_at'], extension_status=row['extension_status'],
            extension_minutes=row['extension_minutes'], created_at=row['created_at']
        )
