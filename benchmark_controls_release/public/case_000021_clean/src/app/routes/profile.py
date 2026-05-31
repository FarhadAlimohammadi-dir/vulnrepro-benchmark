from flask import Blueprint, request, jsonify, session, render_template
from app.middleware.auth import login_required, csrf_required
from app.services.audit_service import AuditService
from app.db import get_connection
import hashlib

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile')
@login_required
def profile_page():
    conn = get_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        settings = conn.execute(
            'SELECT * FROM user_settings WHERE user_id = ?', (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()
    return render_template('profile.html',
                           user=dict(user) if user else {},
                           settings=dict(settings) if settings else {},
                           username=session.get('display_name', session.get('username')))


@profile_bp.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    conn = get_connection()
    try:
        user = conn.execute(
            'SELECT id, username, display_name, email, department, role, created_at, last_login FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
        settings = conn.execute(
            'SELECT theme, notifications_enabled, default_category, ai_persona FROM user_settings WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()

    return jsonify({
        'user': dict(user) if user else {},
        'settings': dict(settings) if settings else {},
    })


@profile_bp.route('/api/profile', methods=['POST'])
@login_required
@csrf_required
def update_profile():
    data = request.get_json() or {}
    display_name = str(data.get('display_name', '')).strip()
    email = str(data.get('email', '')).strip()
    department = str(data.get('department', '')).strip()

    if len(display_name) > 100:
        return jsonify({'error': 'Display name too long'}), 400
    if len(email) > 150:
        return jsonify({'error': 'Email too long'}), 400

    conn = get_connection()
    try:
        if display_name:
            conn.execute('UPDATE users SET display_name = ? WHERE id = ?',
                         (display_name, session['user_id']))
        if email:
            conn.execute('UPDATE users SET email = ? WHERE id = ?',
                         (email, session['user_id']))
        if department:
            conn.execute('UPDATE users SET department = ? WHERE id = ?',
                         (department, session['user_id']))
        conn.commit()
    finally:
        conn.close()

    AuditService.log(session['user_id'], session.get('username'), 'profile_update',
                     ip_address=request.remote_addr)
    return jsonify({'ok': True})


@profile_bp.route('/api/profile/password', methods=['POST'])
@login_required
@csrf_required
def change_password():
    data = request.get_json() or {}
    current_password = str(data.get('current_password', ''))
    new_password = str(data.get('new_password', ''))

    if not current_password or not new_password:
        return jsonify({'error': 'current_password and new_password required'}), 400

    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    conn = get_connection()
    try:
        user = conn.execute(
            'SELECT password_hash FROM users WHERE id = ?', (session['user_id'],)
        ).fetchone()

        current_hash = hashlib.sha256(current_password.encode()).hexdigest()
        if not user or user['password_hash'] != current_hash:
            return jsonify({'error': 'Current password is incorrect'}), 401

        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                     (new_hash, session['user_id']))
        conn.commit()
    finally:
        conn.close()

    AuditService.log(session['user_id'], session.get('username'), 'password_change',
                     ip_address=request.remote_addr)
    return jsonify({'ok': True})


@profile_bp.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT * FROM user_settings WHERE user_id = ?', (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()
    return jsonify({'settings': dict(row) if row else {}})


@profile_bp.route('/api/settings', methods=['POST'])
@login_required
@csrf_required
def update_settings():
    data = request.get_json() or {}
    allowed_themes = {'light', 'dark', 'auto'}
    allowed_personas = {'professional', 'friendly', 'detailed'}

    theme = str(data.get('theme', 'light')).strip()
    notifications = int(bool(data.get('notifications_enabled', True)))
    default_category = str(data.get('default_category', 'general')).strip()
    ai_persona = str(data.get('ai_persona', 'professional')).strip()

    if theme not in allowed_themes:
        theme = 'light'
    if ai_persona not in allowed_personas:
        ai_persona = 'professional'

    conn = get_connection()
    try:
        conn.execute(
            '''INSERT INTO user_settings (user_id, theme, notifications_enabled, default_category, ai_persona)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 theme=excluded.theme,
                 notifications_enabled=excluded.notifications_enabled,
                 default_category=excluded.default_category,
                 ai_persona=excluded.ai_persona''',
            (session['user_id'], theme, notifications, default_category, ai_persona)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True})