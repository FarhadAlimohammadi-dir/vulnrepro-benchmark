import logging
from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify, current_app
from ..database import get_db
import bcrypt
from datetime import datetime

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('api.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', error=None)

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('login.html', error='Username and password are required')

    db = get_db(current_app)
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,)
    ).fetchone()
    db.close()

    if not user:
        logger.warning(f"Failed login attempt for username: {username}")
        return render_template('login.html', error='Invalid credentials')

    if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        logger.warning(f"Invalid password for user: {username}")
        return render_template('login.html', error='Invalid credentials')

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['department'] = user['department']

    db = get_db(current_app)
    db.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), user['id'])
    )
    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
        (user['id'], 'LOGIN', 'auth', f"User {username} logged in", request.remote_addr)
    )
    db.commit()
    db.close()

    logger.info(f"User {username} logged in successfully")

    if user['role'] == 'admin':
        return redirect(url_for('admin.panel'))
    return redirect(url_for('api.dashboard'))


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    user_id = session.get('user_id')
    username = session.get('username')
    if user_id:
        try:
            db = get_db(current_app)
            db.execute(
                "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
                (user_id, 'LOGOUT', 'auth', f"User {username} logged out", request.remote_addr)
            )
            db.commit()
            db.close()
        except Exception:
            pass
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Self-service registration for new employees (requires invite code)."""
    if request.method == 'GET':
        return render_template('login.html', error=None, register=True)

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    invite_code = request.form.get('invite_code', '').strip()

    if not all([username, email, password, invite_code]):
        return jsonify({'error': 'All fields required'}), 400

    # Invite codes are provisioned by HR; hardcoded list for demo
    valid_codes = {'HELPDESK2024', 'NEWSTAFF-Q4', 'ONBOARD-IT'}
    if invite_code not in valid_codes:
        return jsonify({'error': 'Invalid invite code'}), 403

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    try:
        db = get_db(current_app)
        db.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
            (username, email, pw_hash, 'user')
        )
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Username or email already exists'}), 409

    return jsonify({'message': 'Account created. Please log in.'}), 201