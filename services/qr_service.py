import urllib.parse
from services.room_service import RoomService

class QRService:
    @staticmethod
    def generate_room_qr_url(room_id, base_url="http://localhost:5000"):
        room = RoomService.get_room_by_id(room_id)
        if not room:
            return None
        
        # Public scanner URL link
        scan_url = f"{base_url}/qr-scanner/{room_id}?pin={room.qr_pin}"
        
        # Uses standard Google Charts QR API for rendering clean SVG/PNG QR image without extra dependencies
        encoded_url = urllib.parse.quote(scan_url)
        qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_url}"
        
        return {
            'room_id': room.id,
            'room_name': room.name,
            'qr_pin': room.qr_pin,
            'scan_url': scan_url,
            'qr_image_url': qr_image_url
        }
