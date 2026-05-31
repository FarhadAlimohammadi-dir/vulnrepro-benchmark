import logging
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from models.db import get_db, hash_password, verify_password
from models.user import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>TeamHub - Login</title>
<style>
body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
input { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; }
button { width: 100%; padding: 10px; background: #0066cc; color: white; border: none; cursor: pointer; }
.error { color: red; }
</style>
</head>
<body>
<h2>TeamHub Login</h2>
{% for msg in get_flashed_messages() %}<p class="error">{{ msg }}</p>{% endfor %}
<form method="POST">
  <input type="text" name="username" placeholder="Username" required>
  <input type="password" name="password" placeholder="Password" required>
  <button type="submit">Login</button>
</form>
<p><a href="/auth/register">Create account</a></p>
</body>
</html>
'''

REGISTER_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>TeamHub - Register</title>
<style>
body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
input { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; }
button { width: 100%; padding: 10px; background: #0066cc; color: white; border: none; cursor: pointer; }
.error { color: red; }
</style>
</head>
<body>
<h2>Create Account</h2>
{% for msg in get_flashed_messages() %}<p class="error">{{ msg }}</p>{% endfor %}
<form method="POST">
  <input type="text" name="username" placeholder="Username" required>
  <input type="email" name="email" placeholder="Email" required>
  <input type="password" name="password" placeholder="Password" required>
  <input type="text" name="display_name" placeholder="Display Name" required>
  <button type="submit">Register</button>
</form>
<p><a href="/auth/login">Already have an account?</a></p>
</body>
</html>
'''


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.')
            return render_template_string(LOGIN_TEMPLATE), 400

        db = get_db()
        try:
            row = db.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)).fetchone()
        finally:
            db.close()

        if not row or not verify_password(password, row['password_hash']):
            logger.warning("Failed login attempt for username: %s", username)
            flash('Invalid credentials.')
            return render_template_string(LOGIN_TEMPLATE), 401

        user = User.from_row(row)
        login_user(user)

        db = get_db()
        try:
            db.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.utcnow().isoformat(), user.id)
            )
            db.execute(
                'INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)',
                (user.id, 'login', 'User logged in', request.remote_addr, datetime.utcnow().isoformat())
            )
            db.commit()
        finally:
            db.close()

        logger.info("User %s logged in", username)
        next_page = request.args.get('next', '/dashboard')
        return redirect(next_page)

    return render_template_string(LOGIN_TEMPLATE)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()

        if not all([username, email, password, display_name]):
            flash('All fields are required.')
            return render_template_string(REGISTER_TEMPLATE), 400

        if len(username) < 3 or len(username) > 32:
            flash('Username must be 3-32 characters.')
            return render_template_string(REGISTER_TEMPLATE), 400

        db = get_db()
        try:
            existing = db.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?', (username, email)
            ).fetchone()
            if existing:
                flash('Username or email already taken.')
                return render_template_string(REGISTER_TEMPLATE), 409

            db.execute(
                '''INSERT INTO users (username, email, password_hash, display_name, bio, role, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (username, email, hash_password(password), display_name, '', 'member',
                 datetime.utcnow().isoformat())
            )
            db.commit()
            logger.info("New user registered: %s", username)
            flash('Account created. Please log in.')
            return redirect(url_for('auth.login'))
        finally:
            db.close()

    return render_template_string(REGISTER_TEMPLATE)


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info("User %s logged out", current_user.username)
    logout_user()
    return redirect(url_for('auth.login'))