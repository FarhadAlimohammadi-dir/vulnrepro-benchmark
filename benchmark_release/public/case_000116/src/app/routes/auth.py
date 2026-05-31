import bcrypt
import logging
from flask import Blueprint, request, redirect, url_for, render_template, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from ..database import get_db
from ..models import User

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('login.html'), 400

        db = get_db()
        try:
            row = db.execute(
                'SELECT * FROM users WHERE username = ?', (username,)
            ).fetchone()
        finally:
            db.close()

        if row is None:
            flash('Invalid credentials', 'error')
            return render_template('login.html'), 401

        if not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            flash('Invalid credentials', 'error')
            return render_template('login.html'), 401

        user = User(row['id'], row['username'], row['email'], row['password_hash'])
        login_user(user)
        logger.info(f"User {username} logged in from {request.remote_addr}")

        next_page = request.args.get('next')
        return redirect(next_page or url_for('docs.list_documents'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info(f"User {current_user.username} logged out")
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('register.html'), 400

        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('register.html'), 400

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, pw_hash)
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Registration failed for {username}: {e}")
            flash('Username or email already exists', 'error')
            return render_template('register.html'), 409
        finally:
            db.close()

        flash('Account created. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')