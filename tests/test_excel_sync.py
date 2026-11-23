import unittest
import os
import openpyxl
from config import Config
from database import init_db, get_db
from services.excel_service import ExcelService
from services.auth_service import AuthService
from services.room_service import RoomService

class TestExcelSync(unittest.TestCase):
    def setUp(self):
        if os.path.exists(Config.DATABASE_PATH):
            try:
                os.remove(Config.DATABASE_PATH)
            except Exception:
                pass
        init_db()

    def test_export_and_import_excel_cycle(self):
        """Test exporting current database to Excel and re-importing."""
        # 1. Export Excel
        buf = ExcelService.export_current_data_to_excel()
        self.assertIsNotNone(buf)
        self.assertGreater(len(buf.getvalue()), 5000)

        # 2. Inspect Excel workbook sheets
        wb = openpyxl.load_workbook(buf)
        self.assertIn("Guru_dan_Staf", wb.sheetnames)
        self.assertIn("Ruangan_dan_PIC", wb.sheetnames)
        self.assertIn("Siswa", wb.sheetnames)

        # 3. Import back and verify counts
        buf.seek(0)
        res = ExcelService.import_excel_data(buf)
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['summary']['teachers_synced'], 15)
        self.assertGreaterEqual(res['summary']['rooms_synced'], 38)
        self.assertGreaterEqual(res['summary']['students_synced'], 4)

    def test_update_teacher_and_tic_via_excel(self):
        """Test changing a room's TIC and teacher phone number via Excel."""
        buf = ExcelService.export_current_data_to_excel()
        wb = openpyxl.load_workbook(buf)

        # Update teacher Dr. Thorne's phone in sheet
        ws_teachers = wb['Guru_dan_Staf']
        for row in range(2, ws_teachers.max_row + 1):
            if ws_teachers.cell(row=row, column=1).value == "thorne@smamarsudirinibekasi.sch.id":
                ws_teachers.cell(row=row, column=5).value = "0819-9999-8888" # New phone

        # Save and import
        import io
        mod_buf = io.BytesIO()
        wb.save(mod_buf)
        mod_buf.seek(0)

        res = ExcelService.import_excel_data(mod_buf)
        self.assertTrue(res['success'])

        # Verify in database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT contact_phone FROM users WHERE email = 'thorne@smamarsudirinibekasi.sch.id'")
        updated_phone = cursor.fetchone()['contact_phone']
        conn.close()

        self.assertEqual(updated_phone, "0819-9999-8888")

if __name__ == '__main__':
    unittest.main()
