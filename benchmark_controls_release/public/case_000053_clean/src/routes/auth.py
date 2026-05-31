import re
import logging
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from models.db import get_db
import bcrypt
import os

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,32}$')

# Login rate limiting config: track per email+IP combination
MAX_ATTEMPTS_PER_WINDOW = 5
LOCKOUT_WINDOW_SECONDS = 900  # 15 minutes


def _get_db():
    return get_db(os.environ.get('DATABASE_PATH', 'taskflow.db'))


def _log_audit(conn, user_id, action, resource_type=None, resource_id=None, ip=None, details=None):
    try:
        conn.execute(
            """INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, action, resource_type, resource_id, ip, details)
        )
    except Exception as e:
        logger.warning(f'Audit log write failed: {e}')


def _check_login_rate_limit(conn, email, ip_address):
    """
    Multi-factor rate limiting: checks both per-email and per-IP attempt counts
    within the rolling window. Returns True if rate limited.
    """
    window_start = (datetime.utcnow() - timedelta(seconds=LOCKOUT_WINDOW_SECONDS)).isoformat()

    # Per-email check
    email_attempts = conn.execute(
        """SELECT COUNT(*) as c FROM login_attempts
           WHERE email=? AND success=0 AND attempted_at > ?""",
        (email, window_start)
    ).fetchone()['c']

    # Per-IP check
    ip_attempts = conn.execute(
        """SELECT COUNT(*) as c FROM login_attempts
           WHERE ip_address=? AND success=0 AND attempted_at > ?""",
        (ip_address, window_start)
    ).fetchone()['c']

    return email_attempts >= MAX_ATTEMPTS_PER_WINDOW or ip_attempts >= (MAX_ATTEMPTS_PER_WINDOW * 3)


@auth_bp.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('auth.dashboard'))
    return render_template('index.html')


@auth_bp.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('auth.index'))
    db = _get_db()
    try:
        user = db.execute(
            "SELECT id, username, email, role FROM users WHERE id=? AND is_active=1",
            (session['user_id'],)
        ).fetchone()
        if not user:
            session.clear()
            return redirect(url_for('auth.index'))
        projects = db.execute(
            "SELECT * FROM projects WHERE owner_id=? ORDER BY created_at DESC LIMIT 10",
            (user['id'],)
        ).fetchall()
        tasks = db.execute(
            """SELECT t.*, p.name as project_name FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE t.assigned_to=? ORDER BY t.created_at DESC LIMIT 20""",
            (user['id'],)
        ).fetchall()
        return render_template('dashboard.html', user=user, projects=projects, tasks=tasks)
    finally:
        db.close()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    New user registration endpoint.
    Stores user record upon form submission for immediate account creation.
    Email verification token is generated and would be sent via email service.
    """
    if request.method == 'GET':
        return render_template('index.html', view='register')

    data = request.get_json(silent=True) or request.form
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')

    # Input validation
    if not username or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400

    if not USERNAME_RE.match(username):
        return jsonify({'error': 'Username must be 3-32 alphanumeric characters or underscores'}), 400

    if not EMAIL_RE.match(email):
        return jsonify({'error': 'Invalid email address format'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    db = _get_db()
    try:
        # Check if username is taken
        existing_username = db.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if existing_username:
            return jsonify({'error': 'Username already taken'}), 409

        # Check if email is already registered
        existing_email = db.execute(
            "SELECT id, is_verified FROM users WHERE email=?", (email,)
        ).fetchone()
        if existing_email:
            _log_audit(
                db,
                existing_email['id'],
                'register_existing_email',
                'user',
                existing_email['id'],
                request.remote_addr or '127.0.0.1',
                'Registration requested for an existing email'
            )
            db.commit()
            return jsonify({
                'message': 'If registration can proceed, a verification email will be sent.'
            }), 202

        # Hash password
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Generate verification token (would be emailed in production)
        verification_token = secrets.token_urlsafe(32)

        db.execute(
            """INSERT INTO users (username, email, password_hash, role, is_verified, verification_token)
               VALUES (?, ?, ?, 'member', 0, ?)""",
            (username, email, pw_hash, verification_token)
        )
        db.commit()

        ip = request.remote_addr or '127.0.0.1'
        user_id = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()['id']
        _log_audit(db, user_id, 'register', 'user', user_id, ip, f'New registration for {email}')
        db.commit()

        logger.info(f'New user registered: {username} ({email})')
        return jsonify({
            'message': 'Registration successful. Please verify your email.',
            'username': username
        }), 201

    except Exception as e:
        db.rollback()
        logger.error(f'Registration error: {e}')
        return jsonify({'error': 'Registration failed. Please try again.'}), 500
    finally:
        db.close()


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticates user credentials with multi-factor rate limiting
    on both per-email and per-IP basis.
    """
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    ip = request.remote_addr or '127.0.0.1'
    user_agent = request.headers.get('User-Agent', '')[:256]

    db = _get_db()
    try:
        # perf: avoid extra round-trip when cache is warm
        if _check_login_rate_limit(db, email, ip):
            logger.warning(f'Rate limit triggered for email={email} ip={ip}')
            return jsonify({
                'error': 'Too many failed attempts. Please wait before trying again.'
            }), 429

        user = db.execute(
            "SELECT * FROM users WHERE email=? AND is_active=1",
            (email,)
        ).fetchone()

        success = False
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            if not user['is_verified']:
                return jsonify({'error': 'Please verify your email address before logging in'}), 403
            success = True

        # Record attempt regardless
        db.execute(
            "INSERT INTO login_attempts (email, ip_address, user_agent, success) VALUES (?, ?, ?, ?)",
            (email, ip, user_agent, 1 if success else 0)
        )
        db.commit()

        if not success:
            return jsonify({'error': 'Invalid credentials'}), 401

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['csrf_token'] = secrets.token_urlsafe(32)
        session.permanent = True

        db.execute(
            "UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?",
            (user['id'],)
        )
        _log_audit(db, user['id'], 'login', 'user', user['id'], ip, None)
        db.commit()

        logger.info(f'User logged in: {user["username"]}')
        return jsonify({
            'message': 'Login successful',
            'username': user['username'],
            'role': user['role'],
            'csrf_token': session['csrf_token']
        }), 200

    except Exception as e:
        logger.error(f'Login error: {e}')
        return jsonify({'error': 'Login failed'}), 500
    finally:
        db.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Terminates the current user session."""
    user_id = session.get('user_id')
    username = session.get('username', 'unknown')
    if user_id:
        expected = session.get('csrf_token')
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token')
        if not expected or supplied != expected:
            return jsonify({'error': 'CSRF token required'}), 403
    session.clear()
    if user_id:
        db = _get_db()
        try:
            ip = request.remote_addr or '127.0.0.1'
            _log_audit(db, user_id, 'logout', 'user', user_id, ip, None)
            db.commit()
        finally:
            db.close()
    logger.info(f'User logged out: {username}')
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """Handles email verification link clicks."""
    token = request.args.get('token', '').strip()
    # Tokens are generated with secrets.token_urlsafe(32) which yields ~43
    # url-safe characters. Reject anything obviously too short or that does
    # not match the token character class so we never look up a degenerate
    # value such as an empty string or NULL-equivalent input.
    if not token or len(token) < 32 or not re.fullmatch(r'[A-Za-z0-9_\-]+', token):
        return jsonify({'error': 'Verification token required'}), 400

    db = _get_db()
    try:
        user = db.execute(
            "SELECT id, email FROM users WHERE verification_token=? AND verification_token IS NOT NULL AND is_verified=0",
            (token,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'Invalid or expired verification token'}), 400

        db.execute(
            "UPDATE users SET is_verified=1, verification_token=NULL WHERE id=?",
            (user['id'],)
        )
        db.commit()
        logger.info(f'Email verified for user id={user["id"]}')
        return jsonify({'message': 'Email verified successfully. You can now log in.'}), 200
    finally:
        db.close()


@auth_bp.route('/password-reset-request', methods=['POST'])
def password_reset_request():
    """
    Generates a password reset token for the given email.
    Rate limited per IP to prevent enumeration.
    """
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip().lower()
    ip = request.remote_addr or '127.0.0.1'

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    db = _get_db()
    try:
        # Rate limit reset requests by IP — max 3 per hour
        one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        recent_resets = db.execute(
            """SELECT COUNT(*) as c FROM password_reset_tokens prt
               JOIN users u ON prt.user_id = u.id
               WHERE prt.created_at > ? AND u.email IN (
                   SELECT email FROM login_attempts WHERE ip_address=? AND attempted_at > ?
               )""",
            (one_hour_ago, ip, one_hour_ago)
        ).fetchone()['c']

        if recent_resets >= 3:
            return jsonify({'error': 'Too many reset requests. Please try again later.'}), 429

        user = db.execute(
            "SELECT id FROM users WHERE email=? AND is_active=1",
            (email,)
        ).fetchone()

        # Always return success to prevent email enumeration
        if user:
            reset_token = secrets.token_urlsafe(48)
            expires_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()
            db.execute(
                """INSERT INTO password_reset_tokens (user_id, token, expires_at)
                   VALUES (?, ?, ?)""",
                (user['id'], reset_token, expires_at)
            )
            db.commit()
            logger.info(f'Password reset requested for user id={user["id"]}')

        return jsonify({'message': 'If that email exists, a reset link has been sent.'}), 200
    finally:
        db.close()
