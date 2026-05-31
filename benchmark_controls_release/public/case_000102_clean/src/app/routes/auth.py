import logging
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models import get_user_by_username, hash_password, get_user_by_id, get_db, log_action

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    return render_template('index.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html'), 400

        row = get_user_by_username(username)
        if row and row['password_hash'] == hash_password(password):
            from app.models import User
            user = User(row['id'], row['username'], row['email'], bool(row['is_admin']))
            login_user(user)
            log_action(None, user.id, 'login', request.remote_addr,
                       request.headers.get('User-Agent', ''), f'Login: {username}')
            logger.info(f"User {username} logged in from {request.remote_addr}")
            return redirect(url_for('endpoints.dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            logger.warning(f"Failed login attempt for username={username}")
            return render_template('login.html'), 401

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_action(None, current_user.id, 'logout', request.remote_addr,
               request.headers.get('User-Agent', ''), f'Logout: {current_user.username}')
    logout_user()
    return redirect(url_for('auth.index'))


@auth_bp.route('/api/auth/verify', methods=['POST'])
def api_verify():
    """Verify API credentials for programmatic access."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    row = get_user_by_username(username)
    if row and row['password_hash'] == hash_password(password):
        return jsonify({
            'status': 'ok',
            'user': {'id': row['id'], 'username': row['username'], 'email': row['email']}
        })

    return jsonify({'error': 'invalid credentials'}), 401