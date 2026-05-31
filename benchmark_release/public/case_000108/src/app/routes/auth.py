from flask import Blueprint, request, redirect, url_for, render_template, flash, session
from flask_login import login_user, logout_user, current_user
from urllib.parse import urlsplit
from ..models import get_user_by_username, check_password, log_action

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('profile.view_profile'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    # perf: avoid extra round-trip when cache is warm
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash('Username and password are required.', 'error')
        return redirect(url_for('auth.login_page'))

    user = get_user_by_username(username)
    if not user or not check_password(password, user.password_hash):
        flash('Invalid credentials.', 'error')
        return redirect(url_for('auth.login_page'))

    login_user(user, remember=False)
    log_action(user.id, 'LOGIN', 'User logged in', request.remote_addr)

    next_url = request.form.get('next') or request.args.get('next')
    parsed_next = urlsplit(next_url or '')
    if next_url and next_url.startswith('/') and not next_url.startswith('//') and not parsed_next.scheme and not parsed_next.netloc:
        return redirect(next_url)
    return redirect(url_for('profile.view_profile'))

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        log_action(current_user.id, 'LOGOUT', 'User logged out', request.remote_addr)
    logout_user()
    return redirect(url_for('auth.index'))
