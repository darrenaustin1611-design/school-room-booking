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


    def test_single_active_booking_limit(self):
        """Rule Verification: Each student can only hold 1 active booking at a time."""
        # Alex Mercer (id=7, STU1001) books Physics Lab (id=1)
        booking1, err1 = BookingService.create_booking(
            primary_student_id=7,
            room_id=1,
            booking_date="2026-09-10",
            start_time="16:00",
            end_time="17:00",
            purpose="Physics Experiment"
        )
        self.assertIsNotNone(booking1, f"Booking 1 failed: {err1}")
        self.assertIsNone(err1)

        # Alex tries to book another room (Chemistry Lab id=2) while booking1 is PENDING
        booking2, err2 = BookingService.create_booking(
            primary_student_id=7,
            room_id=2,
            booking_date="2026-09-10",
            start_time="17:00",
            end_time="18:00",
            purpose="Chemistry Study"
        )
        self.assertIsNone(booking2)
        self.assertIn("already have an active booking", err2)

    def test_co_booker_active_booking_block(self):
        """Rule Verification: Adding a student who already holds an active booking as a co-booker fails."""
        # Student Maya Lin (id=8, STU1002) creates an active booking
        b1, err1 = BookingService.create_booking(
            primary_student_id=8,
            room_id=3, # Biology Lab
            booking_date="2026-09-11",
            start_time="16:00",
            end_time="17:00",
            purpose="Biology Revision"
        )
        self.assertIsNotNone(b1)

        # Student Leo Tanaka (id=9, STU1003) tries to create a booking adding Maya (STU1002) as co-booker
        b2, err2 = BookingService.create_booking(
            primary_student_id=9,
            room_id=4, # Language Lab
            booking_date="2026-09-11",
            start_time="17:00",
            end_time="18:00",
            purpose="Language Group",
            co_booker_student_numbers=["STU1002"]
        )
        self.assertIsNone(b2)
        self.assertIn("already has an active booking", err2)

    def test_classroom_homeroom_teacher_approval_routing(self):
        """Rule Verification: Classroom bookings route approval to the assigned classroom's Homeroom Teacher."""
        # Class 10-A classroom (room_id=12) has homeroom teacher Mr. David Chen (teacher_id=3)
        room = RoomService.get_room_by_id(12)
        self.assertEqual(room.category, "classroom")
        self.assertEqual(room.teacher_in_charge_id, 3)

        # Student Leo Tanaka (homeroom teacher Mrs. Jenkins id=4) books Class 10-A
        b, err = BookingService.create_booking(
            primary_student_id=9, # Leo Tanaka
            room_id=12,
            booking_date="2026-09-12",
            start_time="16:00",
            end_time="17:00",
            purpose="Group Study in 10-A"
        )
        self.assertIsNotNone(b, err)
        self.assertEqual(b.teacher_in_charge_id, 3) # Mr. Chen approves Class 10-A
        self.assertEqual(b.homeroom_teacher_id, 4) # Mrs. Jenkins gets FYI

    def test_classroom_after_hours_restriction(self):
        """Rule Verification: Classrooms can only be booked after 15:30."""
        # Try booking Class 10-A at 14:00 (during school hours)
        b, err = BookingService.create_booking(
            primary_student_id=7,
            room_id=12,
            booking_date="2026-09-13",
            start_time="14:00",
            end_time="15:00",
            purpose="Afternoon meeting"
        )
        self.assertIsNone(b)
        self.assertIn("after school hours", err)

    def test_grace_period_extension_confirm_coming(self):
        """Rule Verification: Confirming 'Yes I'm coming' extends grace period to +15 mins (total 30 mins)."""
        b, err = BookingService.create_booking(
            primary_student_id=7,
            room_id=1,
            booking_date="2026-09-14",
            start_time="16:00",
            end_time="17:00",
            purpose="Physics test"
        )
        self.assertIsNotNone(b)

        # Approve booking
        ok, msg = BookingService.approve_booking(b.id, teacher_id=1)
        self.assertTrue(ok)

        # Alex confirms coming
        ok_conf, msg_conf = BookingService.confirm_coming(b.id, student_id=7)
        self.assertTrue(ok_conf)

        b_updated = BookingService.get_booking_by_id(b.id)
        self.assertTrue(b_updated.grace_period_extended)
        self.assertEqual(b_updated.get_allowed_grace_minutes(), 30)

if __name__ == '__main__':
    unittest.main()
