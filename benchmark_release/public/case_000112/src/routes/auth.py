import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt

from models.user import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def get_db():
    from flask import current_app
    import sqlite3
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('tasks.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('tasks.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')

        db = get_db()
        row = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if row and bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            user = User(row['id'], row['username'], row['email'], row['password_hash'], row['role'])
            login_user(user, remember=remember)

            db.execute(
                'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
                (user.id, 'user.login', 'Login successful', request.remote_addr)
            )
            db.commit()

            logger.info("User %s logged in from %s", username, request.remote_addr)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('tasks.dashboard'))
        else:
            logger.warning("Failed login attempt for username: %s", username)
            flash('Invalid credentials. Please try again.', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info("User %s logged out", current_user.username)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))