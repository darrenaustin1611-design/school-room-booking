import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'school-room-booking-secret-key-2026')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'school_booking.db')
    
    # System Booking Rules
    MAX_ACTIVE_BOOKINGS_PER_STUDENT = 1
    MAX_BOOKING_HOURS = 2
    ADVANCE_BOOKING_DAYS = 7
    
    # Check-in Grace Period (Minutes)
    INITIAL_GRACE_PERIOD_MINS = 15
    EXTENDED_GRACE_PERIOD_MINS = 15 # Total 30 mins max
    
    # Operating Hours
    CLASSROOM_AFTER_HOURS_START = "15:30"
    FACILITY_OPEN_TIME = "07:00"
    FACILITY_CLOSE_TIME = "20:00"
    
    # Allowed email domain
    SCHOOL_EMAIL_DOMAIN = "@school.edu"
