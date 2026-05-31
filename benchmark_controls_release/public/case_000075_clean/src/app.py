import sqlite3
import threading
import time
import os
import secrets
import hmac
from collections import defaultdict, deque
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from utils.validators import sanitize_string, validate_pin_format
from utils.audit import record_event
from services.device_service import get_device_list, get_device_info
from models.user_model import get_user_profile, update_user_preferences

LOGIN_FAIL_WINDOW_SECONDS = 900
LOGIN_FAIL_THRESHOLD = 5
LOGIN_LOCKOUT_SECONDS = 900

_login_fail_lock = threading.Lock()
_login_fail_history = defaultdict(deque)
_login_lockout_until = {}

# Per-device failed-unlock tracking for throttling.
UNLOCK_FAIL_WINDOW_SECONDS = 900
UNLOCK_FAIL_THRESHOLD = 3
UNLOCK_LOCKOUT_SECONDS = 900

_unlock_fail_lock = threading.Lock()
_unlock_fail_history = defaultdict(deque)
_unlock_lockout_until = {}


def _login_key(username, remote_addr):
    normalized = sanitize_string(username or '').lower()
    return (normalized, remote_addr or 'unknown')


def _login_attempt_state(key, now):
    locked_until = _login_lockout_until.get(key, 0)
    if locked_until and locked_until <= now:
        del _login_lockout_until[key]
        locked_until = 0
    history = _login_fail_history.get(key)
    if history:
        while history and history[0] <= now - LOGIN_FAIL_WINDOW_SECONDS:
            history.popleft()
    return locked_until, len(history) if history else 0


def _record_login_failure(key, now):
    history = _login_fail_history[key]
    history.append(now)
    while history and history[0] <= now - LOGIN_FAIL_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= LOGIN_FAIL_THRESHOLD:
        _login_lockout_until[key] = now + LOGIN_LOCKOUT_SECONDS
        history.clear()


def _clear_login_failures(key):
    _login_fail_history.pop(key, None)
    _login_lockout_until.pop(key, None)


def _unlock_attempt_state(key, now):
    """Return (locked_until, fail_count_in_window). Caller holds the lock."""
    locked_until = _unlock_lockout_until.get(key, 0)
    if locked_until and locked_until <= now:
        del _unlock_lockout_until[key]
        locked_until = 0
    history = _unlock_fail_history.get(key)
    if history:
        while history and history[0] <= now - UNLOCK_FAIL_WINDOW_SECONDS:
            history.popleft()
    return locked_until, len(history) if history else 0


def _record_unlock_failure(key, now):
    history = _unlock_fail_history[key]
    history.append(now)
    while history and history[0] <= now - UNLOCK_FAIL_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= UNLOCK_FAIL_THRESHOLD:
        _unlock_lockout_until[key] = now + UNLOCK_LOCKOUT_SECONDS
        history.clear()


def _clear_unlock_failures(key):
    _unlock_fail_history.pop(key, None)
    _unlock_lockout_until.pop(key, None)

app = Flask(__name__)
# The session secret must come from the environment. In production the app
# refuses to start without it; for local development a random per-process
# value is generated so sessions are not signable from source.
_session_secret = os.environ.get('SESSION_SECRET') or os.environ.get('FLASK_SECRET_KEY')
if not _session_secret:
    if os.environ.get('FLASK_ENV', '').lower() == 'production':
        raise RuntimeError('SESSION_SECRET environment variable is required in production')
    _session_secret = secrets.token_urlsafe(48)
app.secret_key = _session_secret

DB_PATH = '/tmp/smartlock.db'

# TODO: move DB_PATH to environment variable before next release
# TODO: add connection pooling — sqlite3 opens new conn per request

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user',
        email TEXT,
        display_name TEXT,
        created_at INTEGER,
        last_login INTEGER,
        preferences TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY,
        name TEXT,
        pin TEXT,
        location TEXT,
        owner_id INTEGER,
        status TEXT DEFAULT 'active',
        last_accessed INTEGER,
        firmware_version TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        detail TEXT,
        ip_addr TEXT,
        ts INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS access_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        user_id INTEGER,
        day_mask INTEGER,
        start_hour INTEGER,
        end_hour INTEGER
    )''')

    now = int(time.time())

    seeded_users = [
        ('admin', 'admin123', 'admin', 'admin@smartlock.local', 'Administrator'),
        ('jsmith', 'pass1234', 'user', 'jsmith@example.com', 'John Smith'),
        ('mwong', 'mwong@99', 'user', 'mwong@example.com', 'Michelle Wong'),
        ('dryan', 'dynamo22', 'manager', 'dryan@example.com', 'David Ryan'),
        ('tsato', 'sato!888', 'user', 'tsato@example.com', 'Tomoko Sato'),
        ('hpatel', 'hpatel007', 'user', 'hpatel@example.com', 'Harish Patel'),
    ]
    for username, password, role, email, display_name in seeded_users:
        c.execute(
            "INSERT OR IGNORE INTO users "
            "(username, password, role, email, display_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), role, email, display_name, now),
        )

    # Seed devices
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (1, 'FrontDoor', '73918406', 'Entrance Lobby', 1, 'active', 'fw-2.4.1')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (2, 'ServerRoom', '02847615', 'IT Floor 3', 1, 'active', 'fw-2.4.1')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (3, 'WarehouseA', '55129380', 'Building B', 4, 'active', 'fw-2.3.9')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (4, 'ExecSuite', '88304712', 'Floor 12', 4, 'active', 'fw-2.4.1')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (5, 'ParkingGate', '11975824', 'Basement', 1, 'maintenance', 'fw-2.2.0')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (6, 'MailRoom', '33459167', 'Ground Floor', 4, 'active', 'fw-2.4.0')")
    c.execute("INSERT OR IGNORE INTO devices (id, name, pin, location, owner_id, status, firmware_version) VALUES (7, 'RooftopAccess', '66210489', 'Roof', 1, 'inactive', 'fw-2.1.8')")

    # Seed a few access schedules
    c.execute("INSERT OR IGNORE INTO access_schedules (device_id, user_id, day_mask, start_hour, end_hour) VALUES (1, 2, 31, 8, 18)")
    c.execute("INSERT OR IGNORE INTO access_schedules (device_id, user_id, day_mask, start_hour, end_hour) VALUES (2, 4, 31, 7, 20)")
    c.execute("INSERT OR IGNORE INTO access_schedules (device_id, user_id, day_mask, start_hour, end_hour) VALUES (3, 3, 127, 0, 24)")

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', username=session.get('username'))


@app.route('/login_page')
def login_page():
    return render_template('login.html')


# NOTE: /login is also used by mobile clients — keep form-encoded body support
@app.route('/login', methods=['POST'])
def login():
    username = sanitize_string(request.form.get('username') or '')
    password = request.form.get('password') or ''
    throttle_key = _login_key(username, request.remote_addr)
    monotonic_now = time.monotonic()
    with _login_fail_lock:
        locked_until, _ = _login_attempt_state(throttle_key, monotonic_now)
        if locked_until:
            retry_after = max(1, int(locked_until - monotonic_now))
            record_event(None, 'login_locked_out', 'temporary login lockout', request.remote_addr)
            return jsonify({
                'status': 'error',
                'message': 'Invalid credentials',
                'retry_after_seconds': retry_after,
            }), 429

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[1], password):
        with _login_fail_lock:
            _clear_login_failures(throttle_key)
        session['user_id'] = user[0]
        session['username'] = username
        record_event(user[0], 'login', 'successful login', request.remote_addr)
        return jsonify({'status': 'ok', 'message': 'Logged in'}), 200
    with _login_fail_lock:
        _record_login_failure(throttle_key, monotonic_now)
        locked_until, _ = _login_attempt_state(throttle_key, monotonic_now)
    record_event(None, 'login_fail', f'failed attempt for {sanitize_string(username)}', request.remote_addr)
    response = {'status': 'error', 'message': 'Invalid credentials'}
    if locked_until:
        response['retry_after_seconds'] = max(1, int(locked_until - monotonic_now))
        return jsonify(response), 429
    return jsonify(response), 401


@app.route('/logout', methods=['POST'])
def logout():
    uid = session.get('user_id')
    session.clear()
    if uid:
        record_event(uid, 'logout', 'session ended', request.remote_addr)
    return jsonify({'status': 'ok'}), 200


def _caller_role(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row['role'] if row else 'user'


def _can_view_device(user_id, device_id):
    role = _caller_role(user_id)
    if role in ('admin', 'manager'):
        return True
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        d = conn.execute("SELECT owner_id FROM devices WHERE id=?", (device_id,)).fetchone()
        if d and d['owner_id'] == user_id:
            return True
        sch = conn.execute(
            "SELECT 1 FROM access_schedules WHERE device_id=? AND user_id=?",
            (device_id, user_id),
        ).fetchone()
        return sch is not None
    finally:
        conn.close()


@app.route('/api/devices', methods=['GET'])
def list_devices():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    role = _caller_role(user_id)
    devices = get_device_list(DB_PATH)
    if role not in ('admin', 'manager'):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            allowed = {
                row['device_id'] for row in conn.execute(
                    "SELECT device_id FROM access_schedules WHERE user_id=?",
                    (user_id,),
                ).fetchall()
            }
            owned = {
                row['id'] for row in conn.execute(
                    "SELECT id FROM devices WHERE owner_id=?", (user_id,)
                ).fetchall()
            }
        finally:
            conn.close()
        visible = allowed | owned
        devices = [d for d in devices if d.get('id') in visible]
    return jsonify({'devices': devices}), 200


@app.route('/api/devices/<int:device_id>', methods=['GET'])
def device_detail(device_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if not _can_view_device(session['user_id'], device_id):
        return jsonify({'error': 'Forbidden'}), 403
    info = get_device_info(DB_PATH, device_id)
    if info is None:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify({'device': info}), 200


@app.route('/api/unlock', methods=['POST'])
def unlock():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    device_id = data.get('device_id')
    pin_guess = str(data.get('pin', ''))

    user_id = session['user_id']

    if not validate_pin_format(pin_guess):
        return jsonify({'error': 'Invalid PIN format'}), 400

    throttle_key = device_id
    monotonic_now = time.monotonic()
    with _unlock_fail_lock:
        locked_until, _ = _unlock_attempt_state(throttle_key, monotonic_now)
        if locked_until:
            retry_after = max(1, int(locked_until - monotonic_now))
            record_event(user_id, 'unlock_locked_out',
                         f'device {device_id}', request.remote_addr)
            return jsonify({
                'error': 'Too many failed attempts; try again later',
                'retry_after_seconds': retry_after,
            }), 429

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT pin, owner_id, status FROM devices WHERE id=?", (device_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Device not found'}), 404

    # Reject devices that are not in service.
    if row['status'] != 'active':
        conn.close()
        record_event(user_id, 'unlock_blocked',
                     f'device {device_id} status={row["status"]}', request.remote_addr)
        return jsonify({'error': 'Device is not available for unlock'}), 403

    # Authorization: the caller must be the device owner, an admin/manager,
    # or have an active access_schedules grant for the current hour/day.
    user_row = c.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    role = user_row['role'] if user_row else 'user'

    authorized = False
    if role in ('admin', 'manager'):
        authorized = True
    elif row['owner_id'] == user_id:
        authorized = True
    else:
        now = time.localtime()
        # day_mask uses bit 0 = Monday ... bit 6 = Sunday
        day_bit = 1 << now.tm_wday
        sched = c.execute(
            "SELECT 1 FROM access_schedules "
            "WHERE device_id=? AND user_id=? "
            "AND (day_mask & ?) != 0 "
            "AND start_hour <= ? AND end_hour > ?",
            (device_id, user_id, day_bit, now.tm_hour, now.tm_hour)
        ).fetchone()
        authorized = sched is not None

    if not authorized:
        conn.close()
        record_event(user_id, 'unlock_unauthorized',
                     f'device {device_id}', request.remote_addr)
        return jsonify({'error': 'Not authorized for this device'}), 403

    actual_pin = row['pin']
    conn.close()

    pin_matches = hmac.compare_digest(pin_guess, actual_pin)
    elapsed_ms = 0

    if pin_matches:
        with _unlock_fail_lock:
            _clear_unlock_failures(throttle_key)
        record_event(session['user_id'], 'unlock_success', f'device {device_id}', request.remote_addr)
        return jsonify({
            'status': 'unlocked',
            'message': 'Access granted',
            'elapsed_ms': elapsed_ms
        }), 200
    else:
        with _unlock_fail_lock:
            _record_unlock_failure(throttle_key, monotonic_now)
            locked_until, _ = _unlock_attempt_state(throttle_key, monotonic_now)
        record_event(session['user_id'], 'unlock_fail', f'device {device_id}', request.remote_addr)
        response = {
            'status': 'denied',
            'message': 'Invalid PIN',
            'elapsed_ms': elapsed_ms,
        }
        if locked_until:
            response['retry_after_seconds'] = max(1, int(locked_until - monotonic_now))
            return jsonify(response), 429
        return jsonify(response), 401


@app.route('/api/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # TODO: include avatar URL once asset CDN is wired up
    user = get_user_profile(DB_PATH, session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'profile': user}), 200


@app.route('/api/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400
    display_name = sanitize_string(data.get('display_name', ''))
    email = sanitize_string(data.get('email', ''))
    if len(display_name) > 80:
        return jsonify({'error': 'Display name too long'}), 400
    if '@' not in email or len(email) > 120:
        return jsonify({'error': 'Invalid email'}), 400
    update_user_preferences(DB_PATH, session['user_id'], display_name, email)
    record_event(session['user_id'], 'profile_update', 'display_name/email changed', request.remote_addr)
    return jsonify({'status': 'ok'}), 200


@app.route('/api/audit', methods=['GET'])
def audit():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    role = _caller_role(session['user_id'])
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    conn = get_db()
    if role in ('admin', 'manager'):
        rows = conn.execute(
            "SELECT id, user_id, action, detail, ip_addr, ts FROM audit_log "
            "ORDER BY ts DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    else:
        # Non-privileged callers see only their own audit events.
        rows = conn.execute(
            "SELECT id, user_id, action, detail, ip_addr, ts FROM audit_log "
            "WHERE user_id=? ORDER BY ts DESC LIMIT ? OFFSET ?",
            (session['user_id'], limit, offset)
        ).fetchall()
    conn.close()
    return jsonify({'events': [dict(r) for r in rows]}), 200


@app.route('/api/schedules', methods=['GET'])
def list_schedules():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    role = _caller_role(user_id)
    device_id = request.args.get('device_id')
    conn = get_db()
    if device_id:
        device_id_int = int(device_id)
        if not _can_view_device(user_id, device_id_int):
            conn.close()
            return jsonify({'error': 'Forbidden'}), 403
        if role in ('admin', 'manager'):
            rows = conn.execute(
                "SELECT id, device_id, user_id, day_mask, start_hour, end_hour "
                "FROM access_schedules WHERE device_id=?",
                (device_id_int,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, device_id, user_id, day_mask, start_hour, end_hour "
                "FROM access_schedules WHERE device_id=? AND user_id=?",
                (device_id_int, user_id)
            ).fetchall()
    else:
        if role in ('admin', 'manager'):
            rows = conn.execute(
                "SELECT id, device_id, user_id, day_mask, start_hour, end_hour "
                "FROM access_schedules"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, device_id, user_id, day_mask, start_hour, end_hour "
                "FROM access_schedules WHERE user_id=?",
                (user_id,)
            ).fetchall()
    conn.close()
    return jsonify({'schedules': [dict(r) for r in rows]}), 200


@app.route('/health', methods=['GET'])
def health():
    # SRE-2031: used by load balancer; must respond < 200ms
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({'status': 'ok' if db_ok else 'degraded', 'db': db_ok}), 200


@app.route('/api/search', methods=['GET'])
def search_devices():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # TODO: add full-text index when device count exceeds 500
    query = sanitize_string(request.args.get('q', ''))
    if len(query) < 2:
        return jsonify({'error': 'Query too short'}), 400
    conn = get_db()
    user_id = session['user_id']
    role = _caller_role(user_id)
    if role in ('admin', 'manager'):
        rows = conn.execute(
            "SELECT id, name, location, status, firmware_version FROM devices WHERE name LIKE ? OR location LIKE ?",
            (f'%{query}%', f'%{query}%')
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT d.id, d.name, d.location, d.status, d.firmware_version "
            "FROM devices d LEFT JOIN access_schedules s ON s.device_id = d.id "
            "WHERE (d.name LIKE ? OR d.location LIKE ?) "
            "AND (d.owner_id = ? OR s.user_id = ?)",
            (f'%{query}%', f'%{query}%', user_id, user_id)
        ).fetchall()
    conn.close()
    return jsonify({'results': [dict(r) for r in rows]}), 200


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=9000, debug=False)
