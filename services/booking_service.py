import json
from contextlib import closing
from datetime import datetime, timedelta
from database import get_db
from models import Booking, BookingStatus, Notification
from services.room_service import RoomService
from services.auth_service import AuthService

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

        # 2. Validate that the booking ends after it starts on the same date
        try:
            fmt = "%H:%M"
            t1 = datetime.strptime(start_time, fmt)
            t2 = datetime.strptime(end_time, fmt)
            duration_minutes = (t2 - t1).total_seconds() / 60
            if duration_minutes <= 0:
                conn.close()
                return None, "End time must be after start time."
        except ValueError:
            conn.close()
            return None, "Invalid time format. Use HH:MM."

        # 3. Check if primary student holds an active booking (1 active booking limit)
        active_statuses = "('PENDING', 'APPROVED', 'CHECKED_IN', 'PENDING_CONFIRMATION')"
        conn.execute("BEGIN IMMEDIATE")
        
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
        cursor.execute("UPDATE bookings SET status = 'APPROVED' WHERE id = ? AND status = 'PENDING'", (booking_id,))
        if cursor.rowcount == 0:
            conn.close()
            return False, "No pending booking request to approve."
        
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
        cursor.execute("UPDATE bookings SET status = 'REJECTED' WHERE id = ? AND status = 'PENDING'", (booking_id,))
        if cursor.rowcount == 0:
            conn.close()
            return False, "No pending booking request to decline."
        
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
            UPDATE bookings SET status = 'COMPLETED', checked_out_at = ?,
                extension_status = CASE WHEN extension_status = 'PENDING' THEN 'CANCELLED' ELSE extension_status END
            WHERE id = ?
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
    def _extension_conflicts(conn, booking, new_end_time):
        return conn.execute("""
            SELECT id FROM bookings
            WHERE room_id = ? AND booking_date = ? AND id != ?
            AND status IN ('PENDING', 'APPROVED', 'CHECKED_IN', 'PENDING_CONFIRMATION')
            AND start_time < ? AND end_time > ?
        """, (booking.room_id, booking.booking_date, booking.id, new_end_time, booking.end_time)).fetchone() is not None

    @staticmethod
    def request_extension(booking_id, student_id, extra_minutes):
        try:
            extra_minutes = int(extra_minutes)
        except (ValueError, TypeError, OverflowError):
            return False, "Choose a valid extension duration."
        if not 0 < extra_minutes < 1440:
            return False, "Choose a positive extension duration within the same date."

        with closing(get_db()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            if not row or row['status'] != BookingStatus.CHECKED_IN:
                return False, "Must be checked in to request a time extension."

            booking = BookingService._instantiate_booking(row)
            if not booking.is_authorized_student(student_id):
                return False, "Unauthorized."
            if booking.extension_status == 'PENDING':
                return False, "An extension request is already awaiting approval."

            current_end = datetime.strptime(f"{booking.booking_date} {booking.end_time}", "%Y-%m-%d %H:%M")
            new_end = current_end + timedelta(minutes=extra_minutes)
            if new_end.date() != current_end.date():
                return False, "Booking extensions must end on the same date."
            new_end_time = new_end.strftime("%H:%M")
            if BookingService._extension_conflicts(conn, booking, new_end_time):
                return False, "Extension unavailable: another student has booked the room for the subsequent slot."

            conn.execute("""
                UPDATE bookings SET extension_status = 'PENDING', extension_minutes = ? WHERE id = ?
            """, (extra_minutes, booking_id))
            conn.execute("""
                INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
                VALUES (?, 'Extension Request', ?, 'APPROVAL_REQUEST', ?, ?)
            """, (booking.teacher_in_charge_id,
                  f"Student requested +{extra_minutes} mins extension for booking #{booking_id}.",
                  booking_id, datetime.now().isoformat()))

        return True, f"Extension request (+{extra_minutes} mins) sent to Teacher-in-Charge!"

    @staticmethod
    def approve_extension(booking_id, teacher_id):
        return BookingService._decide_extension(booking_id, teacher_id, approve=True)

    @staticmethod
    def reject_extension(booking_id, teacher_id, reason="No reason provided"):
        return BookingService._decide_extension(booking_id, teacher_id, approve=False, reason=reason)

    @staticmethod
    def _decide_extension(booking_id, teacher_id, approve, reason=""):
        with closing(get_db()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            if not row or row['teacher_in_charge_id'] != teacher_id:
                return False, "Unauthorized."
            booking = BookingService._instantiate_booking(row)
            if booking.status != BookingStatus.CHECKED_IN or booking.extension_status != 'PENDING':
                return False, "No pending extension request for this active booking."

            if approve:
                if not 0 < booking.extension_minutes < 1440:
                    return False, "The requested duration is invalid."
                current_end = datetime.strptime(f"{booking.booking_date} {booking.end_time}", "%Y-%m-%d %H:%M")
                new_end = current_end + timedelta(minutes=booking.extension_minutes)
                if new_end.date() != current_end.date():
                    return False, "Booking extensions must end on the same date."
                new_end_time = new_end.strftime("%H:%M")
                if BookingService._extension_conflicts(conn, booking, new_end_time):
                    return False, "Cannot approve extension: the requested time is no longer available."
                conn.execute("""
                    UPDATE bookings SET end_time = ?, extension_status = 'APPROVED' WHERE id = ?
                """, (new_end_time, booking_id))
                title = "Extension Approved!"
                message = f"Your extension for +{booking.extension_minutes} mins was approved. New end time: {new_end_time}."
                result = f"Approved! Booking extended to {new_end_time}."
            else:
                conn.execute("UPDATE bookings SET extension_status = 'REJECTED' WHERE id = ?", (booking_id,))
                title = "Extension Declined"
                message = f"Your extension request was declined. Reason: {reason or 'No reason provided'}. Your booking still ends at {booking.end_time}."
                result = "Extension declined. Original booking end time retained."

            conn.execute("""
                INSERT INTO notifications (user_id, title, message, type, booking_id, created_at)
                VALUES (?, ?, ?, 'STATUS_UPDATE', ?, ?)
            """, (booking.primary_student_id, title, message, booking_id, datetime.now().isoformat()))

        return True, result

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
