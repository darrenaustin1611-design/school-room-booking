from datetime import datetime

class Notification:
    def __init__(self, id, user_id, title, message, type='INFO', booking_id=None, is_read=False, created_at=None):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.message = message
        self.type = type # APPROVAL_REQUEST, FYI_NOTIFICATION, CHECKIN_PROMPT, STATUS_UPDATE, INFO
        self.booking_id = booking_id
        self.is_read = bool(is_read)
        self.created_at = created_at or datetime.now().isoformat()

    def mark_as_read(self):
        self.is_read = True

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'booking_id': self.booking_id,
            'is_read': self.is_read,
            'created_at': self.created_at
        }
