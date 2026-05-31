import logging
from flask import Blueprint, request, redirect, url_for, render_template, flash, session
from flask_login import login_user, logout_user, login_required, current_user

from models import get_user_by_username, verify_password, User, get_db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


def _log_audit(user_id, action, detail, ip):
    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO audit_log (user_id, action, detail, ip_address) VALUES (?,?,?,?)',
                (user_id, action, detail, ip)
            )
    except Exception as e:
        logger.error(f'Audit log error: {e}')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))

    # legacy: kept for v1 API clients still in the wild
    next_url = request.args.get('next') or request.form.get('next', '')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html', next_url=next_url)

        row = get_user_by_username(username)
        if not row or not verify_password(password, row['password_hash']):
            flash('Invalid username or password.', 'error')
            _log_audit(None, 'login_failed', f'username={username}', request.remote_addr)
            return render_template('login.html', next_url=next_url)

        user = User(row)
        login_user(user, remember=request.form.get('remember') == 'on')
        _log_audit(user.id, 'login_success', f'username={username}', request.remote_addr)
        logger.info(f'User {username} logged in from {request.remote_addr}')

        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)

        return redirect(url_for('dashboard.home'))

    return render_template('login.html', next_url=next_url)


@auth_bp.route('/logout')
@login_required
def logout():
    # legacy: kept for v1 API clients still in the wild
    next_url = request.args.get('continue', '')
    username = current_user.username
    user_id = current_user.id
    logout_user()
    _log_audit(user_id, 'logout', f'username={username}', request.remote_addr)
    logger.info(f'User {username} logged out')

    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)

    return redirect(url_for('auth.login'))


@auth_bp.route('/password-reset', methods=['GET', 'POST'])
def password_reset():
    """Initiate password reset flow."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            # In production this would send an email
            logger.info(f'Password reset requested for {email}')
            flash('If that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('password_reset.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Update user profile information."""
    if request.method == 'POST':
        company = request.form.get('company', '').strip()
        email = request.form.get('email', '').strip()

        if not email or '@' not in email:
            flash('Valid email is required.', 'error')
            return render_template('profile.html')

        try:
            with get_db() as conn:
                conn.execute(
                    'UPDATE users SET company = ?, email = ? WHERE id = ?',
                    (company, email, current_user.id)
                )
            _log_audit(current_user.id, 'profile_update', f'email={email}', request.remote_addr)
            flash('Profile updated successfully.', 'success')
        except Exception as e:
            logger.error(f'Profile update error: {e}')
            flash('Error updating profile.', 'error')

    return render_template('profile.html')
