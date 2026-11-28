import io
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import werkzeug.security as security
from database import get_db

class ExcelService:
    @staticmethod
    def export_current_data_to_excel():
        """
        Exports current Teachers, Rooms, and Students from the SQLite database
        into a beautifully formatted Excel workbook (.xlsx) with 3 sheets:
        1. Guru_dan_Staf
        2. Ruangan_dan_PIC
        3. Siswa
        """
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Dark Indigo
        header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        regular_font = Font(name="Arial", size=10)
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        conn = get_db()
        cursor = conn.cursor()

        # ==========================================
        # Sheet 1: Guru_dan_Staf
        # ==========================================
        ws_teachers = wb.create_sheet(title="Guru_dan_Staf")
        teacher_headers = [
            "Email", "Nama_Lengkap", "Departemen_Mapel", "Lokasi_Ruang_Kerja", 
            "No_Telepon_WA", "Jam_Konsultasi", "Wali_Kelas_Untuk", "Password"
        ]
        ws_teachers.append(teacher_headers)

        cursor.execute("""
            SELECT u.*, r.name as assigned_class_name 
            FROM users u
            LEFT JOIN rooms r ON u.assigned_homeroom_classroom_id = r.id
            WHERE u.role = 'teacher'
            ORDER BY u.id ASC
        """)
        teachers = cursor.fetchall()
        for t in teachers:
            ws_teachers.append([
                t['email'] or '',
                t['name'] or '',
                t['department'] or '',
                t['office_location'] or '',
                t['contact_phone'] or '',
                t['office_hours'] or '',
                t['assigned_class_name'] or '',
                '' # Blank password by default (means unchanged)
            ])

        # ==========================================
        # Sheet 2: Ruangan_dan_PIC
        # ==========================================
        ws_rooms = wb.create_sheet(title="Ruangan_dan_PIC")
        room_headers = [
            "Nama_Ruangan", "Kategori", "Kapasitas", "Lokasi", 
            "Email_PIC_Guru", "PIN_QR", "Hanya_Luar_Jam_Sekolah", "Deskripsi"
        ]
        ws_rooms.append(room_headers)

        cursor.execute("""
            SELECT r.*, u.email as tic_email 
            FROM rooms r
            LEFT JOIN users u ON r.teacher_in_charge_id = u.id
            ORDER BY r.id ASC
        """)
        rooms = cursor.fetchall()
        for r in rooms:
            after_hours_str = "YA" if r['requires_after_hours_only'] == 1 else "TIDAK"
            ws_rooms.append([
                r['name'] or '',
                r['category'] or 'classroom',
                r['capacity'] or 30,
                r['location'] or '',
                r['tic_email'] or '',
                r['qr_pin'] or '1234',
                after_hours_str,
                r['description'] or ''
            ])

        # ==========================================
        # Sheet 3: Siswa
        # ==========================================
        ws_students = wb.create_sheet(title="Siswa")
        student_headers = [
            "NISN_NIS", "Nama_Lengkap", "Email", "Kelas", "Password"
        ]
        ws_students.append(student_headers)

        cursor.execute("""
            SELECT u.*, r.name as classroom_name 
            FROM users u
            LEFT JOIN rooms r ON u.homeroom_classroom_id = r.id
            WHERE u.role = 'student'
            ORDER BY u.id ASC
        """)
        students = cursor.fetchall()
        for s in students:
            class_val = s['classroom_name'] or s['grade_level'] or ''
            ws_students.append([
                s['student_id_number'] or '',
                s['name'] or '',
                s['email'] or '',
                class_val,
                '' # Blank password means default/unchanged
            ])

        conn.close()

        # Format and auto-adjust widths for all sheets
        for sheet in [ws_teachers, ws_rooms, ws_students]:
            sheet.views.sheetView[0].showGridLines = True
            # Header styling
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
            sheet.row_dimensions[1].height = 28

            # Data rows styling
            for row_idx in range(2, sheet.max_row + 1):
                sheet.row_dimensions[row_idx].height = 20
                for col_idx in range(1, sheet.max_column + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    cell.font = regular_font
                    cell.border = thin_border
                    if col_idx in (1, 5, 6, 7):
                        cell.alignment = Alignment(vertical="center")
                    else:
                        cell.alignment = Alignment(vertical="center")

            # Column auto-width calculation
            for col in sheet.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    val_str = str(cell.value or '')
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                sheet.column_dimensions[col_letter].width = max(max_len + 4, 15)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def import_excel_data(file_stream):
        """
        Reads uploaded .xlsx workbook, validates sheets, and syncs
        teachers, rooms, and students into the database.
        Returns a dict: {'success': bool, 'summary': dict, 'errors': list}
        """
        try:
            wb = openpyxl.load_workbook(file_stream, data_only=True)
        except Exception as e:
            return {
                'success': False,
                'message': f"Failed to open Excel file. Please ensure it is a valid .xlsx file: {str(e)}",
                'summary': {},
                'errors': [str(e)]
            }

        conn = get_db()
        cursor = conn.cursor()
        default_pw = security.generate_password_hash("password123")

        errors = []
        summary = {
            'teachers_synced': 0,
            'rooms_synced': 0,
            'students_synced': 0,
            'homerooms_linked': 0
        }

        # -------------------------------------------------------------
        # 1. Process Sheet 'Guru_dan_Staf'
        # -------------------------------------------------------------
        if 'Guru_dan_Staf' in wb.sheetnames:
            ws_t = wb['Guru_dan_Staf']
            t_rows = list(ws_t.iter_rows(values_only=True))
            if len(t_rows) > 1:
                # Header mapping
                header = [str(c or '').strip().lower() for c in t_rows[0]]
                try:
                    email_idx = header.index("email")
                    name_idx = header.index("nama_lengkap")
                except ValueError:
                    email_idx, name_idx = 0, 1

                dept_idx = header.index("departemen_mapel") if "departemen_mapel" in header else 2
                loc_idx = header.index("lokasi_ruang_kerja") if "lokasi_ruang_kerja" in header else 3
                phone_idx = header.index("no_telepon_wa") if "no_telepon_wa" in header else 4
                hours_idx = header.index("jam_konsultasi") if "jam_konsultasi" in header else 5
                walas_idx = header.index("wali_kelas_untuk") if "wali_kelas_untuk" in header else 6
                pw_idx = header.index("password") if "password" in header else 7

                for row_num, r in enumerate(t_rows[1:], start=2):
                    if not r or not any(r):
                        continue
                    email = str(r[email_idx] or '').strip()
                    name = str(r[name_idx] or '').strip()
                    if not email or not name:
                        continue

                    dept = str(r[dept_idx] or '').strip() if dept_idx < len(r) else ''
                    loc = str(r[loc_idx] or '').strip() if loc_idx < len(r) else ''
                    phone = str(r[phone_idx] or '').strip() if phone_idx < len(r) else ''
                    hours = str(r[hours_idx] or '').strip() if hours_idx < len(r) else ''
                    walas_room_name = str(r[walas_idx] or '').strip() if walas_idx < len(r) else ''
                    pw_raw = str(r[pw_idx] or '').strip() if pw_idx < len(r) else ''

                    pw_hash = security.generate_password_hash(pw_raw) if pw_raw else None

                    # Check if teacher exists
                    cursor.execute("SELECT id, password_hash FROM users WHERE LOWER(email) = LOWER(?)", (email,))
                    existing = cursor.fetchone()
                    if existing:
                        final_pw = pw_hash if pw_hash else existing['password_hash']
                        cursor.execute("""
                            UPDATE users 
                            SET name = ?, password_hash = ?, role = 'teacher',
                                department = ?, office_location = ?, contact_phone = ?, office_hours = ?
                            WHERE id = ?
                        """, (name, final_pw, dept, loc, phone, hours, existing['id']))
                    else:
                        final_pw = pw_hash if pw_hash else default_pw
                        cursor.execute("""
                            INSERT INTO users (name, email, password_hash, role, department, office_location, contact_phone, office_hours)
                            VALUES (?, ?, ?, 'teacher', ?, ?, ?, ?)
                        """, (name, email, final_pw, dept, loc, phone, hours))
                    summary['teachers_synced'] += 1

        conn.commit()

        # -------------------------------------------------------------
        # 2. Process Sheet 'Ruangan_dan_PIC'
        # -------------------------------------------------------------
        if 'Ruangan_dan_PIC' in wb.sheetnames:
            ws_r = wb['Ruangan_dan_PIC']
            r_rows = list(ws_r.iter_rows(values_only=True))
            if len(r_rows) > 1:
                header = [str(c or '').strip().lower() for c in r_rows[0]]
                name_idx = header.index("nama_ruangan") if "nama_ruangan" in header else 0
                cat_idx = header.index("kategori") if "kategori" in header else 1
                cap_idx = header.index("kapasitas") if "kapasitas" in header else 2
                loc_idx = header.index("lokasi") if "lokasi" in header else 3
                tic_idx = header.index("email_pic_guru") if "email_pic_guru" in header else 4
                pin_idx = header.index("pin_qr") if "pin_qr" in header else 5
                after_idx = header.index("hanya_luar_jam_sekolah") if "hanya_luar_jam_sekolah" in header else 6
                desc_idx = header.index("deskripsi") if "deskripsi" in header else 7

                for row_num, r in enumerate(r_rows[1:], start=2):
                    if not r or not any(r):
                        continue
                    room_name = str(r[name_idx] or '').strip()
                    if not room_name:
                        continue

                    cat = str(r[cat_idx] or 'classroom').strip()
                    try:
                        cap = int(r[cap_idx]) if r[cap_idx] is not None else 30
                    except (ValueError, TypeError):
                        cap = 30
                    loc = str(r[loc_idx] or '').strip()
                    tic_email = str(r[tic_idx] or '').strip()
                    pin = str(r[pin_idx] or '1234').strip()
                    after_raw = str(r[after_idx] or 'TIDAK').strip().upper()
                    after_val = 1 if after_raw in ('YA', 'YES', '1', 'TRUE') else 0
                    desc = str(r[desc_idx] or '').strip()

                    # Find TIC user id by email
                    tic_id = None
                    if tic_email:
                        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (tic_email,))
                        tic_row = cursor.fetchone()
                        if tic_row:
                            tic_id = tic_row['id']
                        else:
                            errors.append(f"Rooms sheet, row {row_num}: PIC email '{tic_email}' was not found in the system.")

                    # Default TIC to admin or first teacher if not found
                    if not tic_id:
                        cursor.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1")
                        first_teacher = cursor.fetchone()
                        tic_id = first_teacher['id'] if first_teacher else 1

                    # Icon selection
                    icon_map = {
                        'science_lab': 'flask',
                        'classroom': 'chalkboard-teacher',
                        'event_space': 'theater-masks',
                        'media_room': 'podcast' if 'podcast' in room_name.lower() else 'film',
                        'sports_facility': 'basketball-ball'
                    }
                    icon = icon_map.get(cat, 'chalkboard-teacher')

                    # Check if room exists
                    cursor.execute("SELECT id FROM rooms WHERE LOWER(name) = LOWER(?)", (room_name,))
                    existing_room = cursor.fetchone()
                    if existing_room:
                        cursor.execute("""
                            UPDATE rooms 
                            SET category = ?, capacity = ?, location = ?, teacher_in_charge_id = ?, 
                                qr_pin = ?, requires_after_hours_only = ?, description = ?, icon = ?
                            WHERE id = ?
                        """, (cat, cap, loc, tic_id, pin, after_val, desc, icon, existing_room['id']))
                    else:
                        cursor.execute("""
                            INSERT INTO rooms (name, category, capacity, location, teacher_in_charge_id, qr_pin, requires_after_hours_only, description, icon, extra_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
                        """, (room_name, cat, cap, loc, tic_id, pin, after_val, desc, icon))
                    summary['rooms_synced'] += 1

        conn.commit()

        # -------------------------------------------------------------
        # 3. Synchronize Homeroom Teachers to Classrooms
        # (Using 'Wali_Kelas_Untuk' column from Sheet 1)
        # -------------------------------------------------------------
        if 'Guru_dan_Staf' in wb.sheetnames:
            ws_t = wb['Guru_dan_Staf']
            t_rows = list(ws_t.iter_rows(values_only=True))
            if len(t_rows) > 1:
                header = [str(c or '').strip().lower() for c in t_rows[0]]
                email_idx = header.index("email") if "email" in header else 0
                walas_idx = header.index("wali_kelas_untuk") if "wali_kelas_untuk" in header else 6

                for r in t_rows[1:]:
                    if not r or not any(r):
                        continue
                    email = str(r[email_idx] or '').strip()
                    walas_room = str(r[walas_idx] or '').strip() if walas_idx < len(r) else ''
                    if email and walas_room:
                        # Find room id
                        cursor.execute("SELECT id FROM rooms WHERE LOWER(name) = LOWER(?)", (walas_room,))
                        rm_row = cursor.fetchone()
                        if rm_row:
                            cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
                            u_row = cursor.fetchone()
                            if u_row:
                                cursor.execute("UPDATE users SET assigned_homeroom_classroom_id = ? WHERE id = ?", (rm_row['id'], u_row['id']))
                                # Also update room's teacher in charge if it is a classroom
                                cursor.execute("UPDATE rooms SET teacher_in_charge_id = ? WHERE id = ?", (u_row['id'], rm_row['id']))
                                summary['homerooms_linked'] += 1

        conn.commit()

        # -------------------------------------------------------------
        # 4. Process Sheet 'Siswa'
        # -------------------------------------------------------------
        if 'Siswa' in wb.sheetnames:
            ws_s = wb['Siswa']
            s_rows = list(ws_s.iter_rows(values_only=True))
            if len(s_rows) > 1:
                header = [str(c or '').strip().lower() for c in s_rows[0]]
                nis_idx = header.index("nisn_nis") if "nisn_nis" in header else 0
                name_idx = header.index("nama_lengkap") if "nama_lengkap" in header else 1
                email_idx = header.index("email") if "email" in header else 2
                class_idx = header.index("kelas") if "kelas" in header else 3
                pw_idx = header.index("password") if "password" in header else 4

                for row_num, r in enumerate(s_rows[1:], start=2):
                    if not r or not any(r):
                        continue
                    nis = str(r[nis_idx] or '').strip()
                    name = str(r[name_idx] or '').strip()
                    email = str(r[email_idx] or '').strip()
                    class_val = str(r[class_idx] or '').strip() if class_idx < len(r) else ''
                    pw_raw = str(r[pw_idx] or '').strip() if pw_idx < len(r) else ''

                    if not nis and not email:
                        continue

                    # Auto generate email if empty
                    if not email and nis:
                        email = f"student{nis}@example.com"

                    pw_hash = security.generate_password_hash(pw_raw) if pw_raw else None

                    # Find Classroom and Homeroom Teacher
                    homeroom_class_id = None
                    homeroom_teacher_id = None

                    if class_val:
                        # Try exact or formatted name (e.g. '11-b' -> 'Class 11-B')
                        search_term = class_val
                        if not search_term.lower().startswith('class'):
                            search_term = f"Class {class_val.upper()}"
                        
                        cursor.execute("""
                            SELECT id, teacher_in_charge_id FROM rooms 
                            WHERE LOWER(name) = LOWER(?) OR LOWER(name) = LOWER(?)
                        """, (class_val, search_term))
                        rm_row = cursor.fetchone()
                        if rm_row:
                            homeroom_class_id = rm_row['id']
                            homeroom_teacher_id = rm_row['teacher_in_charge_id']

                    # Check if student exists by NIS or Email
                    cursor.execute("""
                        SELECT id, password_hash FROM users 
                        WHERE (student_id_number = ? AND student_id_number IS NOT NULL AND student_id_number != '')
                           OR LOWER(email) = LOWER(?)
                    """, (nis, email))
                    existing_s = cursor.fetchone()

                    grade_str = class_val
                    if existing_s:
                        final_pw = pw_hash if pw_hash else existing_s['password_hash']
                        cursor.execute("""
                            UPDATE users 
                            SET name = ?, email = ?, password_hash = ?, role = 'student',
                                student_id_number = ?, grade_level = ?,
                                homeroom_classroom_id = ?, homeroom_teacher_id = ?
                            WHERE id = ?
                        """, (name, email, final_pw, nis, grade_str, homeroom_class_id, homeroom_teacher_id, existing_s['id']))
                    else:
                        final_pw = pw_hash if pw_hash else default_pw
                        cursor.execute("""
                            INSERT INTO users (name, email, password_hash, role, student_id_number, grade_level, homeroom_classroom_id, homeroom_teacher_id)
                            VALUES (?, ?, ?, 'student', ?, ?, ?, ?)
                        """, (name, email, final_pw, nis, grade_str, homeroom_class_id, homeroom_teacher_id))

                    summary['students_synced'] += 1

        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f"Synchronization complete: {summary['teachers_synced']} teachers/staff, {summary['rooms_synced']} rooms, and {summary['students_synced']} students updated.",
            'summary': summary,
            'errors': errors
        }
