import hashlib
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, g
from app.db import get_connection
from app.services.audit_service import AuditService

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'DocuMind AI', 'version': '2.4.1'})


@auth_bp.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or request.form
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', '')).strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if len(username) > 64 or len(password) > 128:
        return jsonify({'error': 'Invalid input length'}), 400

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_connection()
    try:
        user = conn.execute(
            'SELECT id, username, role, display_name FROM users WHERE username = ? AND password_hash = ?',
            (username, pw_hash)
        ).fetchone()
    finally:
        conn.close()

    if not user:
        AuditService.log(None, username, 'login_failed', ip_address=request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401

    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['display_name'] = user['display_name'] or user['username']

    AuditService.log(user['id'], user['username'], 'login_success', ip_address=request.remote_addr)

    # Update last_login
    conn = get_connection()
    try:
        conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True, 'username': user['username'], 'role': user['role']})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        AuditService.log(session['user_id'], session.get('username'), 'logout',
                         ip_address=request.remote_addr)
    session.clear()
    return jsonify({'ok': True})


@auth_bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('dashboard.html',
                           username=session.get('display_name', session.get('username', '')),
                           role=session.get('role', 'user'))