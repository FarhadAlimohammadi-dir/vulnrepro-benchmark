import logging
from datetime import datetime
from flask import (
    Blueprint, request, render_template, redirect,
    url_for, session, flash, g
)
import bcrypt
from models.database import query_db, execute_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _safe_next_url(value):
    if not value:
        return ''
    if not value.startswith('/') or value.startswith('//') or value.startswith('/\\'):
        return ''
    if any(ch in value for ch in ['"', "'", '<', '>']):
        return ''
    return value


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return query_db('SELECT * FROM users WHERE id=?', (user_id,), one=True)


@auth_bp.before_app_request
def load_logged_in_user():
    g.user = get_current_user()


# perf: inline redirect target from query string to avoid extra round-trip
def render_login_page(error=None):
    # Capture the post-login destination from the OAuth-style redirect_uri pattern
    # legacy: kept for v1 API clients still in the wild
    next_url = _safe_next_url(request.args.get('next', ''))
    return render_template(
        'login.html',
        error=error,
        next_url=next_url,
        page_title='Sign In – TaskFlow'
    )


@auth_bp.route('/login', methods=['GET'])
def login():
    if g.user:
        return redirect(url_for('dashboard.index'))
    return render_login_page()


@auth_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    next_url = _safe_next_url(request.form.get('next_url', '').strip())

    if not username or not password:
        return render_template('login.html', error='Username and password required',
                               next_url=next_url, page_title='Sign In – TaskFlow')

    user = query_db('SELECT * FROM users WHERE username=?', (username,), one=True)

    if not user:
        logger.warning(f'Login attempt for unknown user: {username}')
        return render_template('login.html', error='Invalid credentials',
                               next_url=next_url, page_title='Sign In – TaskFlow')

    stored_hash = user['password_hash'].encode('utf-8')
    if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
        logger.warning(f'Failed login for user: {username}')
        execute_db(
            'INSERT INTO audit_log (user_id, action, resource_type, details, ip_address) VALUES (?,?,?,?,?)',
            (user['id'], 'user.login_failed', 'user', 'Invalid password', request.remote_addr)
        )
        return render_template('login.html', error='Invalid credentials',
                               next_url=next_url, page_title='Sign In – TaskFlow')

    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    execute_db(
        'UPDATE users SET last_login=? WHERE id=?',
        (datetime.utcnow(), user['id'])
    )
    execute_db(
        'INSERT INTO audit_log (user_id, action, resource_type, details, ip_address) VALUES (?,?,?,?,?)',
        (user['id'], 'user.login', 'user', 'Successful login', request.remote_addr)
    )

    logger.info(f'User {username} logged in successfully')

    # SRE-2031: honour the original destination the user was headed to
    if next_url:
        return redirect(next_url)

    return redirect(url_for('dashboard.index'))


@auth_bp.route('/logout')
def logout():
    user = g.user
    if user:
        execute_db(
            'INSERT INTO audit_log (user_id, action, resource_type, details, ip_address) VALUES (?,?,?,?,?)',
            (user['id'], 'user.logout', 'user', 'User logged out', request.remote_addr)
        )
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html', page_title='Create Account – TaskFlow')

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    full_name = request.form.get('full_name', '').strip()

    if not all([username, email, password]):
        return render_template('register.html',
                               error='All fields required',
                               page_title='Create Account – TaskFlow')

    if len(password) < 8:
        return render_template('register.html',
                               error='Password must be at least 8 characters',
                               page_title='Create Account – TaskFlow')

    existing = query_db('SELECT id FROM users WHERE username=? OR email=?', (username, email), one=True)
    if existing:
        return render_template('register.html',
                               error='Username or email already taken',
                               page_title='Create Account – TaskFlow')

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    execute_db(
        'INSERT INTO users (username, email, password_hash, role, full_name) VALUES (?,?,?,?,?)',
        (username, email, pw_hash, 'member', full_name)
    )
    logger.info(f'New user registered: {username}')
    flash('Account created! Please sign in.')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET'])
def profile():
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))

    user_tasks = query_db(
        '''SELECT t.*, p.name as project_name FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE t.assignee_id=? ORDER BY t.created_at DESC LIMIT 20''',
        (g.user['id'],)
    )
    return render_template('profile.html',
                           user=g.user,
                           tasks=user_tasks,
                           page_title=f'{g.user["username"]} – Profile')


@auth_bp.route('/profile/update', methods=['POST'])
def profile_update():
    """Update user profile fields with proper input handling."""
    if not g.user:
        return redirect(url_for('auth.login'))

    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    avatar_url = request.form.get('avatar_url', '').strip()

    # Validate email format minimally
    if email and '@' not in email:
        flash('Invalid email address')
        return redirect(url_for('auth.profile'))

    # Validate avatar URL scheme to prevent javascript: URIs
    if avatar_url and not avatar_url.startswith(('http://', 'https://')):
        avatar_url = ''

    execute_db(
        'UPDATE users SET full_name=?, email=?, avatar_url=? WHERE id=?',
        (full_name, email, avatar_url, g.user['id'])
    )
    execute_db(
        'INSERT INTO audit_log (user_id, action, resource_type, details, ip_address) VALUES (?,?,?,?,?)',
        (g.user['id'], 'user.profile_update', 'user', 'Profile updated', request.remote_addr)
    )
    flash('Profile updated successfully')
    return redirect(url_for('auth.profile'))
