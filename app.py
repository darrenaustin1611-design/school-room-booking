import os
import hashlib
from datetime import date, datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from config import Config
from database import init_db, get_db
from services.auth_service import AuthService
from services.room_service import RoomService
from services.booking_service import BookingService
from services.excel_service import ExcelService

app = Flask(__name__)
app.config.from_object(Config)

def build_asset_version():
    """Create a stable cache key that changes whenever local CSS or JS changes."""
    digest = hashlib.sha256()
    for relative_path in ('static/css/main.css', 'static/js/main.js',
                          'static/css/admin-room-directory.css', 'static/js/admin-room-directory.js'):
        with open(os.path.join(app.root_path, relative_path), 'rb') as asset:
            digest.update(asset.read())
    return digest.hexdigest()[:12]

SCHOOL_TIMEZONE = timezone(timedelta(hours=7))

# Ensure database is initialized on startup
with app.app_context():
    init_db()

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return AuthService.get_user_by_id(user_id)

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user(), asset_version=build_asset_version())

# --- Routes ---

@app.route('/')
@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    if user.is_admin():
        return redirect(url_for('admin_data_center'))

    conn = get_db()
    cursor = conn.cursor()

    active_booking = None
    active_booking_room = None
    active_booking_tic = None
    pending_approvals = []
    pending_approvals_count = 0
    notifications = []

    if user.is_student() or user.is_teacher():
        user_bookings = BookingService.get_user_bookings(user.id)
        for b in user_bookings:
            if b.is_active():
                active_booking = b
                active_booking_room = RoomService.get_room_by_id(b.room_id)
                active_booking_tic = AuthService.get_user_by_id(b.teacher_in_charge_id)
                break

    if user.is_teacher():
        cursor.execute("""
            SELECT * FROM bookings WHERE teacher_in_charge_id = ?
            AND (status = 'PENDING' OR (status = 'CHECKED_IN' AND extension_status = 'PENDING'))
            ORDER BY id DESC
        """, (user.id,))
        rows = cursor.fetchall()
        for r in rows:
            b = BookingService._instantiate_booking(r)
            stu = AuthService.get_user_by_id(b.primary_student_id)
            rm = RoomService.get_room_by_id(b.room_id)
            pending_approvals.append({'booking': b, 'student': stu, 'room': rm})
        pending_approvals_count = len(pending_approvals)

    # Fetch User Notifications
    cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user.id,))
    notif_rows = cursor.fetchall()
    notifications = [dict(r) for r in notif_rows]

    conn.close()

    return render_template('dashboard.html',
                           active_page='dashboard',
                           active_booking=active_booking,
                           active_booking_room=active_booking_room,
                           active_booking_tic=active_booking_tic,
                           pending_approvals=pending_approvals,
                           pending_approvals_count=pending_approvals_count,
                           notifications=notifications)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        user, err = AuthService.authenticate(email, password)
        if err:
            flash(err, 'error')
            return render_template('login.html')

        session['user_id'] = user.id
        flash(f"Welcome back, {user.name}!", 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Signed out successfully.", 'info')
    return redirect(url_for('login'))

@app.route('/rooms')
def rooms_catalog():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    category = request.args.get('category', 'all')
    search = request.args.get('q', '').strip()
    search_terms = search.casefold().split()
    rooms = RoomService.get_all_rooms(category=category)

    room_items = []
    for r in rooms:
        searchable = f'{r.name} {r.location} {r.description}'.casefold()
        if not all(term in searchable for term in search_terms):
            continue
        tic = AuthService.get_user_by_id(r.teacher_in_charge_id)
        room_items.append({'room': r, 'tic': tic})

    return render_template('rooms.html', active_page='rooms', room_items=room_items,
                           current_category=category, search=search)

@app.route('/rooms/<int:room_id>')
def room_detail(room_id, booking_draft=None):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    room = RoomService.get_room_by_id(room_id)
    if not room:
        flash("Room not found.", 'error')
        return redirect(url_for('rooms_catalog'))

    school_now = datetime.now(SCHOOL_TIMEZONE)
    today = school_now.date()
    selected_date = (booking_draft or {}).get('booking_date') or request.args.get('date', today.isoformat())
    try:
        selected_day = max(today, date.fromisoformat(selected_date))
    except ValueError:
        selected_day = today
    selected_date = selected_day.isoformat()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM bookings WHERE room_id = ? AND booking_date = ?
        AND status IN ('PENDING', 'APPROVED', 'CHECKED_IN', 'PENDING_CONFIRMATION')
        ORDER BY start_time ASC
    """, (room_id, selected_date))
    existing_bookings = [BookingService._instantiate_booking(r) for r in cursor.fetchall()]
    conn.close()

    tic = AuthService.get_user_by_id(room.teacher_in_charge_id)
    earliest_start = room.booking_start_time
    if selected_day == today:
        next_minute = school_now + timedelta(minutes=1)
        earliest_start = max(earliest_start, next_minute.strftime('%H:%M')) if next_minute.date() == today else '23:59'
    available_windows = []
    next_start = earliest_start
    for booking in existing_bookings:
        if next_start < booking.start_time:
            available_windows.append({'start': next_start, 'end': booking.start_time})
        next_start = max(next_start, booking.end_time)
    if next_start < '23:59':
        available_windows.append({'start': next_start, 'end': '23:59'})

    return render_template('room_detail.html',
                           active_page='rooms',
                           room=room,
                           tic=tic,
                           existing_bookings=existing_bookings,
                           selected_date=selected_date,
                           date_label=selected_day.strftime('%A, %d %B %Y'),
                           booking_draft=booking_draft or {},
                           available_windows=available_windows,
                           next_date=(selected_day + timedelta(days=1)).isoformat() if selected_day < date.max else None,
                           today_str=today.isoformat()), 422 if booking_draft else 200

@app.route('/book', methods=['POST'])
def create_booking_route():
    user = get_current_user()
    if not user:
        flash("Only logged-in students and teachers can request room bookings.", 'error')
        return redirect(url_for('login'))
    if not (user.is_student() or user.is_teacher()):
        flash("Only students and teachers can request room bookings.", 'error')
        return redirect(url_for('rooms_catalog'))

    room_id = request.form.get('room_id', type=int)
    if room_id is None:
        flash("Choose a room before requesting a booking.", 'error')
        return redirect(url_for('rooms_catalog'))

    booking_date = request.form.get('booking_date', '')
    start_time = request.form.get('start_time', '')
    end_time = request.form.get('end_time', '')
    purpose = request.form.get('purpose', '').strip()

    try:
        booking_day = date.fromisoformat(booking_date)
    except ValueError:
        booking_day = None

    school_now = datetime.now(SCHOOL_TIMEZONE)
    if booking_day is None or booking_day < school_now.date():
        err = "Choose today or a future date."
    elif not start_time or not end_time or not purpose:
        err = "Choose a start and end time and enter the purpose of your booking."
    else:
        try:
            start_time = datetime.strptime(start_time, '%H:%M').strftime('%H:%M')
            end_time = datetime.strptime(end_time, '%H:%M').strftime('%H:%M')
        except ValueError:
            err = "Choose a valid start and end time."
        else:
            if int(start_time[3:]) % 10 or int(end_time[3:]) % 10:
                err = "Start and end times must use 10-minute intervals."
            elif booking_day == school_now.date() and start_time <= school_now.strftime('%H:%M'):
                err = "That start time has passed. Choose a later time or another date."
            else:
                _, err = BookingService.create_booking(
                    primary_student_id=user.id,
                    room_id=room_id,
                    booking_date=booking_day.isoformat(),
                    start_time=start_time,
                    end_time=end_time,
                    purpose=purpose
                )

    if err:
        draft = dict(booking_date=booking_date, start_time=start_time, end_time=end_time, purpose=purpose, error=err)
        return room_detail(room_id, booking_draft=draft)

    flash("Booking request submitted! Sent to Teacher-in-Charge for approval.", 'success')
    return redirect(url_for('my_bookings'))

@app.route('/my-bookings')
def my_bookings():
    user = get_current_user()
    if not user or (not user.is_student() and not user.is_teacher() and not user.is_admin()):
        return redirect(url_for('login'))

    user_bookings = BookingService.get_user_bookings(user.id)
    bookings_data = []

    for b in user_bookings:
        rm = RoomService.get_room_by_id(b.room_id)
        tic = AuthService.get_user_by_id(b.teacher_in_charge_id)
        stu = AuthService.get_user_by_id(b.primary_student_id)
        bookings_data.append({'booking': b, 'room': rm, 'tic': tic, 'student': stu})

    return render_template('my_bookings.html', active_page='my_bookings', bookings=bookings_data)

@app.route('/approvals')
def approvals_queue():
    user = get_current_user()
    if not user or not user.is_teacher():
        flash("Access restricted to Faculty staff.", 'error')
        return redirect(url_for('dashboard'))

    conn = get_db()
    cursor = conn.cursor()

    # 1. Pending Approvals where user is TIC
    cursor.execute("""
        SELECT * FROM bookings WHERE teacher_in_charge_id = ?
        AND (status = 'PENDING' OR (status = 'CHECKED_IN' AND extension_status = 'PENDING'))
        ORDER BY id DESC
    """, (user.id,))
    pending_rows = cursor.fetchall()
    pending_list = []
    for r in pending_rows:
        b = BookingService._instantiate_booking(r)
        stu = AuthService.get_user_by_id(b.primary_student_id)
        rm = RoomService.get_room_by_id(b.room_id)
        pending_list.append({'booking': b, 'student': stu, 'room': rm})

    # 2. FYI list for Homeroom Teacher
    cursor.execute("""
        SELECT * FROM bookings WHERE homeroom_teacher_id = ? AND teacher_in_charge_id != ? ORDER BY id DESC LIMIT 10
    """, (user.id, user.id))
    fyi_rows = cursor.fetchall()
    fyi_list = []
    for r in fyi_rows:
        b = BookingService._instantiate_booking(r)
        stu = AuthService.get_user_by_id(b.primary_student_id)
        rm = RoomService.get_room_by_id(b.room_id)
        tic = AuthService.get_user_by_id(b.teacher_in_charge_id)
        fyi_list.append({'booking': b, 'student': stu, 'room': rm, 'tic': tic})

    history = cursor.execute("""
        SELECT h.*, u.name AS booker_name, r.name AS room_name
        FROM pic_history h JOIN users u ON u.id=h.booker_id JOIN rooms r ON r.id=h.room_id
        WHERE h.pic_id=? ORDER BY h.id DESC LIMIT 25
    """, (user.id,)).fetchall()
    conn.close()

    return render_template('approvals.html', active_page='approvals', pending_list=pending_list,
                           fyi_list=fyi_list, history=history)

@app.route('/teachers')
def teachers_directory():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY name ASC")
    t_rows = cursor.fetchall()

    teacher_list = []
    for tr in t_rows:
        t_obj = AuthService._instantiate_user(tr)
        cursor.execute("SELECT * FROM rooms WHERE teacher_in_charge_id = ?", (t_obj.id,))
        m_rooms = [RoomService._instantiate_room(rm) for rm in cursor.fetchall()]

        homeroom_room = None
        if t_obj.assigned_homeroom_classroom_id:
            cursor.execute("SELECT name FROM rooms WHERE id = ?", (t_obj.assigned_homeroom_classroom_id,))
            hr_row = cursor.fetchone()
            if hr_row:
                homeroom_room = hr_row['name']

        teacher_list.append({
            'teacher': t_obj, 
            'managed_rooms': m_rooms,
            'homeroom_classroom': homeroom_room
        })

    conn.close()
    return render_template('teachers.html', active_page='teachers', teacher_list=teacher_list)

@app.route('/qr-scanner/<int:room_id>')
def qr_scanner_page(room_id):
    if not get_current_user():
        return redirect(url_for('login'))
    room = RoomService.get_room_by_id(room_id)
    if not room:
        return "Invalid Room", 440
    pin = request.args.get('pin', room.qr_pin)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>QR Check-In - {room.name}</title></head>
    <body style="font-family: sans-serif; background: #0f172a; color: white; text-align: center; padding: 3rem;">
        <h2>Scanned QR for {room.name}</h2>
        <p>Room PIN Code: <strong style="color: #06b6d4; font-size: 1.5rem;">{pin}</strong></p>
        <p>Please enter this 4-digit PIN on your Student Dashboard check-in modal!</p>
        <a href="/dashboard" style="color: #6366f1;">Go to My Dashboard</a>
    </body>
    </html>
    """

# --- API JSON Endpoints ---

@app.route('/api/bookings/<int:booking_id>/start-use', methods=['POST'])
@app.route('/api/bookings/<int:booking_id>/check-in', methods=['POST'])
def start_use_api(booking_id):
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    
    ok, msg = BookingService.check_in(booking_id, user.id)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/bookings/<int:booking_id>/finish-use', methods=['POST'])
@app.route('/api/bookings/<int:booking_id>/check-out', methods=['POST'])
def finish_use_api(booking_id):
    user = get_current_user()
    if not user:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Authentication required.'}), 401
        return redirect(url_for('login'))

    ok, msg = BookingService.check_out(booking_id, user.id)
    if request.is_json:
        return jsonify({'success': ok, 'message': msg})
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('my_bookings'))

@app.route('/api/bookings/<int:booking_id>/confirm-coming', methods=['POST'])
def confirm_coming_api(booking_id):
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401

    ok, msg = BookingService.confirm_coming(booking_id, user.id)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/bookings/<int:booking_id>/extend', methods=['POST'])
def extend_booking_api(booking_id):
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401

    data = request.get_json() or {}
    extra_minutes = data.get('extra_minutes', 15)
    
    ok, msg = BookingService.request_extension(booking_id, user.id, extra_minutes)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/approvals/<int:booking_id>/action', methods=['POST'])
def approval_action_api(booking_id):
    user = get_current_user()
    if not user or not user.is_teacher():
        return jsonify({'success': False, 'message': 'Teacher authorization required.'}), 403

    data = request.get_json() or {}
    action = data.get('action')
    reason = data.get('reason', 'No reason provided')

    if action == 'APPROVE_EXTENSION':
        ok, msg = BookingService.approve_extension(booking_id, user.id)
    elif action == 'REJECT_EXTENSION':
        ok, msg = BookingService.reject_extension(booking_id, user.id, reason)
    elif action == 'APPROVE':
        ok, msg = BookingService.approve_booking(booking_id, user.id)
    elif action == 'REJECT':
        ok, msg = BookingService.reject_booking(booking_id, user.id, reason)
    else:
        return jsonify({'success': False, 'message': 'Invalid approval action.'}), 400

    return jsonify({'success': ok, 'message': msg})

# --- Admin & Excel Sync Routes ---

@app.route('/admin')
@app.route('/admin/data')
def admin_data_center():
    user = get_current_user()
    if not user or not user.is_admin():
        flash("Access restricted to the Administrator & School Office.", "error")
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # 1. Teachers with Homeroom and Managed Rooms
    cursor.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY id ASC")
    t_rows = cursor.fetchall()
    teacher_data = []
    for tr in t_rows:
        t_obj = AuthService._instantiate_user(tr)
        cursor.execute("SELECT * FROM rooms WHERE teacher_in_charge_id = ?", (t_obj.id,))
        m_rooms = [RoomService._instantiate_room(rm) for rm in cursor.fetchall()]

        homeroom_name = None
        if t_obj.assigned_homeroom_classroom_id:
            cursor.execute("SELECT name FROM rooms WHERE id = ?", (t_obj.assigned_homeroom_classroom_id,))
            hr = cursor.fetchone()
            if hr:
                homeroom_name = hr['name']

        teacher_data.append({
            'teacher': t_obj,
            'managed_rooms': m_rooms,
            'homeroom_name': homeroom_name
        })

    # 2. Students with Homeroom Teacher
    cursor.execute("SELECT * FROM users WHERE role = 'student' ORDER BY id ASC")
    s_rows = cursor.fetchall()
    student_data = []
    for sr in s_rows:
        s_obj = AuthService._instantiate_user(sr)
        walas_obj = AuthService.get_user_by_id(s_obj.homeroom_teacher_id) if s_obj.homeroom_teacher_id else None

        classroom_name = s_obj.grade_level
        if s_obj.homeroom_classroom_id:
            cursor.execute("SELECT name FROM rooms WHERE id = ?", (s_obj.homeroom_classroom_id,))
            cr = cursor.fetchone()
            if cr:
                classroom_name = cr['name']

        student_data.append({
            'student': s_obj,
            'walas': walas_obj,
            'classroom_name': classroom_name
        })

    # 3. Rooms with TIC
    cursor.execute("SELECT * FROM rooms ORDER BY id ASC")
    r_rows = cursor.fetchall()
    room_data = []
    for rr in r_rows:
        rm = RoomService._instantiate_room(rr)
        tic = AuthService.get_user_by_id(rm.teacher_in_charge_id)
        room_data.append({
            'room': rm,
            'tic': tic
        })

    conn.close()

    return render_template('admin_data.html',
                           active_page='admin_data',
                           teachers=t_rows,
                           teacher_data=teacher_data,
                           students=s_rows,
                           student_data=student_data,
                           rooms=r_rows,
                           room_data=room_data)

@app.route('/admin/download-excel')
def admin_download_excel():
    user = get_current_user()
    if not user or not user.is_admin():
        flash("Access restricted to the Administrator & School Office.", "error")
        return redirect(url_for('login'))

    buf = ExcelService.export_current_data_to_excel()
    filename = f"Data_Sekolah_Marsudirini_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/admin/upload-excel', methods=['POST'])
def admin_upload_excel():
    user = get_current_user()
    if not user or not user.is_admin():
        flash("Access restricted to the Administrator & School Office.", "error")
        return redirect(url_for('login'))

    if 'excel_file' not in request.files:
        flash("No file was uploaded.", "error")
        return redirect(url_for('admin_data_center'))

    file = request.files['excel_file']
    if file.filename == '':
        flash("Select an Excel file first.", "error")
        return redirect(url_for('admin_data_center'))

    if not file.filename.lower().endswith('.xlsx'):
        flash("The file must use the .xlsx format (Microsoft Excel / Google Sheets).", "error")
        return redirect(url_for('admin_data_center'))

    result = ExcelService.import_excel_data(file.stream)
    if result['success']:
        flash(result['message'], 'success')
        if result.get('errors'):
            for err in result['errors']:
                flash(f"Warning: {err}", 'warning')
    else:
        flash(result.get('message', 'An error occurred while processing the Excel file.'), 'error')

    return redirect(url_for('admin_data_center'))

@app.route('/quick-demo-login/<int:user_id>')
def quick_demo_login(user_id):
    user = get_current_user()
    if not user or not user.is_admin():
        flash("Administrator access required.", 'error')
        return redirect(url_for('login' if not user else 'dashboard'))
    u = AuthService.get_user_by_id(user_id)
    if not u:
        flash("User account not found.", "error")
        return redirect(url_for('login'))

    session['user_id'] = u.id
    flash(f"Switched to demo account: {u.name} ({u.role.upper()})", "success")
    if u.is_admin():
        return redirect(url_for('admin_data_center'))
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
