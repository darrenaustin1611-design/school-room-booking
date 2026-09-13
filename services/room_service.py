import json
from database import get_db
from models import Room, ScienceLab, MediaRoom, SportsFacility, Classroom
from services.auth_service import AuthService

class RoomService:
    @staticmethod
    def get_all_rooms(category=None):
        conn = get_db()
        cursor = conn.cursor()
        if category and category != 'all':
            cursor.execute("SELECT * FROM rooms WHERE category = ? ORDER BY name ASC", (category,))
        else:
            cursor.execute("SELECT * FROM rooms ORDER BY category ASC, name ASC")
        rows = cursor.fetchall()
        conn.close()

        rooms = []
        for r in rows:
            rooms.append(RoomService._instantiate_room(r))
        return rooms

    @staticmethod
    def get_room_by_id(room_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return RoomService._instantiate_room(row)

    @staticmethod
    def get_room_tic_details(room_id):
        room = RoomService.get_room_by_id(room_id)
        if not room:
            return None
        tic_id = room.teacher_in_charge_id
        return AuthService.get_user_by_id(tic_id)

    @staticmethod
    def _instantiate_room(row):
        category = row['category']
        extra = json.loads(row['extra_data']) if row['extra_data'] else {}
        
        if category == 'science_lab':
            return ScienceLab(
                id=row['id'], name=row['name'], capacity=row['capacity'], location=row['location'],
                teacher_in_charge_id=row['teacher_in_charge_id'], lab_type=extra.get('lab_type', 'General'),
                safety_guidelines=extra.get('safety_guidelines', 'Follow general lab protocol.'),
                qr_pin=row['qr_pin'], description=row['description']
            )
        elif category == 'media_room':
            return MediaRoom(
                id=row['id'], name=row['name'], capacity=row['capacity'], location=row['location'],
                teacher_in_charge_id=row['teacher_in_charge_id'], equipment_list=extra.get('equipment', []),
                qr_pin=row['qr_pin'], description=row['description']
            )
        elif category == 'sports_facility':
            return SportsFacility(
                id=row['id'], name=row['name'], capacity=row['capacity'], location=row['location'],
                teacher_in_charge_id=row['teacher_in_charge_id'], court_type=extra.get('court_type', 'Standard Court'),
                qr_pin=row['qr_pin'], description=row['description']
            )
        elif category == 'classroom':
            return Classroom(
                id=row['id'], name=row['name'], capacity=row['capacity'], location=row['location'],
                assigned_homeroom_teacher_id=row['teacher_in_charge_id'], grade_level=extra.get('grade_level', 'General'),
                qr_pin=row['qr_pin'], description=row['description']
            )
        
        return Room(
            id=row['id'], name=row['name'], category=row['category'], capacity=row['capacity'],
            location=row['location'], teacher_in_charge_id=row['teacher_in_charge_id'],
            qr_pin=row['qr_pin'], requires_after_hours_only=bool(row['requires_after_hours_only']),
            description=row['description'], icon=row['icon']
        )
