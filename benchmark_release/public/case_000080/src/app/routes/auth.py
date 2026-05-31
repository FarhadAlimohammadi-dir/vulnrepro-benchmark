import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import get_db, User
from app import login_manager

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
    return None


@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if not row:
            logger.warning("Login attempt for unknown user: %s", username)
            return jsonify({'error': 'Invalid credentials'}), 401

        user = User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])

        if not user.check_password(password):
            logger.warning("Failed login for user: %s", username)
            return jsonify({'error': 'Invalid credentials'}), 401

        login_user(user, remember=True)
        logger.info("User %s logged in successfully", username)

        conn = get_db()
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)',
            (user.id, 'login', 'auth', request.remote_addr)
        )
        conn.commit()
        conn.close()

        return jsonify({'message': 'Login successful', 'user': {'id': user.id, 'username': user.username, 'role': user.role}})

    return render_template('login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logger.info("User %s logged out", current_user.username)
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    conn = get_db()
    reports = conn.execute(
        'SELECT id, title, status, created_at FROM reports WHERE owner_id = ? ORDER BY created_at DESC LIMIT 5',
        (current_user.id,)
    ).fetchall()
    conn.close()
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'role': current_user.role,
        },
        'recent_reports': [dict(r) for r in reports]
    })


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    allowed_fields = {'email'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    conn = get_db()
    for field, value in updates.items():
        conn.execute(f'UPDATE users SET {field} = ? WHERE id = ?', (value, current_user.id))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Profile updated'})