import unittest
import os
import sqlite3
import json
from config import Config
from database import init_db, get_db
from services.auth_service import AuthService
from services.room_service import RoomService
from services.booking_service import BookingService

class TestSchoolBookingOOPRules(unittest.TestCase):
    def setUp(self):
        # Ensure fresh database isolation for each test
        if os.path.exists(Config.DATABASE_PATH):
            try:
                os.remove(Config.DATABASE_PATH)
            except Exception:
                pass
        init_db()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE role = 'student' ORDER BY id ASC")
        self.students = cursor.fetchall()
        cursor.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY id ASC")
        self.teachers = cursor.fetchall()
        cursor.execute("SELECT * FROM rooms WHERE category = 'classroom' ORDER BY id ASC")
        self.classrooms = cursor.fetchall()
        cursor.execute("SELECT * FROM rooms WHERE name LIKE '%Physics%'")
        self.physics_lab = cursor.fetchone()
        cursor.execute("SELECT * FROM rooms WHERE name LIKE '%Chemistry%'")
        self.chem_lab = cursor.fetchone()
        cursor.execute("SELECT * FROM rooms WHERE name LIKE '%Biology%'")
        self.bio_lab = cursor.fetchone()
        cursor.execute("SELECT * FROM rooms WHERE name LIKE '%Language%'")
        self.lang_lab = cursor.fetchone()
        conn.close()

    def test_single_active_booking_limit(self):
        """Rule Verification: Each student can only hold 1 active booking at a time."""
        stu1 = self.students[0]
        # Student books Physics Lab
        booking1, err1 = BookingService.create_booking(
            primary_student_id=stu1['id'],
            room_id=self.physics_lab['id'],
            booking_date="2026-09-10",
            start_time="16:00",
            end_time="17:00",
            purpose="Physics Experiment"
        )
        self.assertIsNotNone(booking1, f"Booking 1 failed: {err1}")
        self.assertIsNone(err1)

        # Student tries to book another room (Chemistry Lab) while booking1 is PENDING
        booking2, err2 = BookingService.create_booking(
            primary_student_id=stu1['id'],
            room_id=self.chem_lab['id'],
            booking_date="2026-09-10",
            start_time="17:00",
            end_time="18:00",
            purpose="Chemistry Study"
        )
        self.assertIsNone(booking2)
        self.assertIn("already have an active booking", err2)

    def test_start_and_finish_use_cycle(self):
        """Rule Verification: Mulai Pakai and Selesai Pakai without QR/PIN for authorized student & admin."""
        stu1 = self.students[0]
        # Student creates booking
        b1, err1 = BookingService.create_booking(
            primary_student_id=stu1['id'],
            room_id=self.bio_lab['id'],
            booking_date="2026-09-11",
            start_time="16:00",
            end_time="17:00",
            purpose="Biology Revision"
        )
        self.assertIsNotNone(b1)
        
        # TIC approves booking
        ok_app, _ = BookingService.approve_booking(b1.id, b1.teacher_in_charge_id)
        self.assertTrue(ok_app)

        # Mulai Pakai (direct confirmation without PIN/QR)
        ok_start, msg_start = BookingService.check_in(b1.id, stu1['id'])
        self.assertTrue(ok_start, msg_start)
        b_in_use = BookingService.get_booking_by_id(b1.id)
        self.assertEqual(b_in_use.status, "CHECKED_IN")

        # Selesai Pakai
        ok_fin, msg_fin = BookingService.check_out(b1.id, stu1['id'])
        self.assertTrue(ok_fin, msg_fin)
        b_done = BookingService.get_booking_by_id(b1.id)
        self.assertEqual(b_done.status, "COMPLETED")

    def test_classroom_homeroom_teacher_approval_routing(self):
        """Rule Verification: Classroom bookings route approval to the assigned classroom's Homeroom Teacher."""
        cls = self.classrooms[0] # First classroom
        self.assertEqual(cls['category'], "classroom")
        
        stu = self.students[0]
        b, err = BookingService.create_booking(
            primary_student_id=stu['id'],
            room_id=cls['id'],
            booking_date="2026-09-12",
            start_time="16:00",
            end_time="17:00",
            purpose="Group Study in Classroom"
        )
        self.assertIsNotNone(b, err)
        self.assertEqual(b.teacher_in_charge_id, cls['teacher_in_charge_id'])
        self.assertEqual(b.homeroom_teacher_id, stu['homeroom_teacher_id'])

    def test_classroom_after_hours_restriction(self):
        """Rule Verification: Classrooms can only be booked from 14:30."""
        cls = self.classrooms[0]
        stu = self.students[0]
        # Reject a start one minute before classroom booking opens
        b, err = BookingService.create_booking(
            primary_student_id=stu['id'],
            room_id=cls['id'],
            booking_date="2026-09-13",
            start_time="14:29",
            end_time="15:00",
            purpose="Afternoon meeting"
        )
        self.assertIsNone(b)
        self.assertIn("after school hours", err)

    def test_grace_period_extension_confirm_coming(self):
        """Rule Verification: Confirming 'Yes I'm coming' extends grace period to +15 mins (total 30 mins)."""
        stu = self.students[0]
        b, err = BookingService.create_booking(
            primary_student_id=stu['id'],
            room_id=self.physics_lab['id'],
            booking_date="2026-09-14",
            start_time="16:00",
            end_time="17:00",
            purpose="Physics test"
        )
        self.assertIsNotNone(b)

        # Approve booking by room's TIC
        ok, msg = BookingService.approve_booking(b.id, teacher_id=b.teacher_in_charge_id)
        self.assertTrue(ok)

        # Student confirms coming
        ok_conf, msg_conf = BookingService.confirm_coming(b.id, student_id=stu['id'])
        self.assertTrue(ok_conf)

        b_updated = BookingService.get_booking_by_id(b.id)
        self.assertTrue(b_updated.grace_period_extended)
        self.assertEqual(b_updated.get_allowed_grace_minutes(), 30)

if __name__ == '__main__':
    unittest.main()
