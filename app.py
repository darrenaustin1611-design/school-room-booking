import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from config import Config
from database import init_db, get_db
from services.auth_service import AuthService
from services.room_service import RoomService
from services.booking_service import BookingService
from services.qr_service import QRService

app = Flask(__name__)
app.config.from_object(Config)

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
    return dict(current_user=get_current_user())

# --- Routes ---

@app.route('/')
@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    active_booking = None
    active_booking_room = None
    active_booking_tic = None
    pending_approvals = []
    pending_approvals_count = 0
    notifications = []

    if user.is_student():
        user_bookings = BookingService.get_user_bookings(user.id)
        for b in user_bookings:
            if b.is_active():
                active_booking = b
                active_booking_room = RoomService.get_room_by_id(b.room_id)
                active_booking_tic = AuthService.get_user_by_id(b.teacher_in_charge_id)
                break

    elif user.is_teacher():
        cursor.execute("""
            SELECT * FROM bookings WHERE teacher_in_charge_id = ? AND status = 'PENDING' ORDER BY id DESC
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
    rooms = RoomService.get_all_rooms(category=category)

    room_items = []
    for r in rooms:
        tic = AuthService.get_user_by_id(r.teacher_in_charge_id)
        room_items.append({'room': r, 'tic': tic})

    return render_template('rooms.html', active_page='rooms', room_items=room_items, current_category=category)

@app.route('/rooms/<int:room_id>')
def room_detail(room_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    room = RoomService.get_room_by_id(room_id)
    if not room:
        flash("Room not found.", 'error')
        return redirect(url_for('rooms_catalog'))

    today_str = datetime.now().strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today_str)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM bookings WHERE room_id = ? AND booking_date = ? AND status IN ('PENDING', 'APPROVED', 'CHECKED_IN')
        ORDER BY start_time ASC
    """, (room_id, selected_date))
    existing_bookings = [BookingService._instantiate_booking(r) for r in cursor.fetchall()]
    conn.close()

    tic = AuthService.get_user_by_id(room.teacher_in_charge_id)
    qr_data = QRService.generate_room_qr_url(room_id, base_url=request.host_url.rstrip('/'))

    return render_template('room_detail.html',
                           active_page='rooms',
                           room=room,
                           tic=tic,
                           qr_data=qr_data,
                           existing_bookings=existing_bookings,
                           selected_date=selected_date,
                           today_str=today_str)

@app.route('/book', methods=['POST'])
def create_booking_route():
    user = get_current_user()
    if not user or not user.is_student():
        flash("Only logged-in students can request room bookings.", 'error')
        return redirect(url_for('login'))

    room_id = request.form.get('room_id', type=int)
    booking_date = request.form.get('booking_date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    purpose = request.form.get('purpose', '').strip()
    co_bookers_raw = request.form.get('co_booker_ids', '').strip()

    co_booker_numbers = [x.strip() for x in co_bookers_raw.split(',') if x.strip()] if co_bookers_raw else []

    booking, err = BookingService.create_booking(
        primary_student_id=user.id,
        room_id=room_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
        co_booker_student_numbers=co_booker_numbers
    )

    if err:
        flash(err, 'error')
        return redirect(url_for('room_detail', room_id=room_id, date=booking_date))

    flash("Booking request submitted! Sent to Teacher-in-Charge for approval.", 'success')
    return redirect(url_for('my_bookings'))

@app.route('/my-bookings')
def my_bookings():
    user = get_current_user()
    if not user or not user.is_student():
        return redirect(url_for('login'))

    user_bookings = BookingService.get_user_bookings(user.id)
    bookings_data = []

    for b in user_bookings:
        rm = RoomService.get_room_by_id(b.room_id)
        tic = AuthService.get_user_by_id(b.teacher_in_charge_id)
        bookings_data.append({'booking': b, 'room': rm, 'tic': tic})

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
        SELECT * FROM bookings WHERE teacher_in_charge_id = ? AND status = 'PENDING' ORDER BY id DESC
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

    conn.close()

    return render_template('approvals.html', active_page='approvals', pending_list=pending_list, fyi_list=fyi_list)

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
        teacher_list.append({'teacher': t_obj, 'managed_rooms': m_rooms})

    conn.close()
    return render_template('teachers.html', active_page='teachers', teacher_list=teacher_list)

@app.route('/qr-scanner/<int:room_id>')
def qr_scanner_page(room_id):
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

@app.route('/api/bookings/<int:booking_id>/check-in', methods=['POST'])
def check_in_api(booking_id):
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    
    data = request.get_json() or {}
    pin = data.get('pin', '')
    
    ok, msg = BookingService.check_in(booking_id, user.id, pin)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/bookings/<int:booking_id>/check-out', methods=['POST'])
def check_out_booking(booking_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    ok, msg = BookingService.check_out(booking_id, user.id)
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

    if action == 'APPROVE':
        ok, msg = BookingService.approve_booking(booking_id, user.id)
    else:
        ok, msg = BookingService.reject_booking(booking_id, user.id, reason)

    return jsonify({'success': ok, 'message': msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
