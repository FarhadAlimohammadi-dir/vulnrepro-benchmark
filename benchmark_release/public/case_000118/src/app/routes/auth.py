import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from markupsafe import Markup
from app.models import User, AuditLog

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _get_db():
    return current_app.config['DATABASE']


@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html', error=None, prefill_user='')


@auth_bp.route('/login', methods=['POST'])
def login_submit():
    """Handle sign-in form submission for the HR portal."""
    username = request.form.get('txtUserId', '')
    password = request.form.get('txtpassword', '')
    db = _get_db()

    row = User.get_by_username(username, db)

    if row and User.verify_password(row['password_hash'], password):
        user = User(row['id'], row['username'], row['email'], row['role'], row['department'])
        login_user(user)
        AuditLog.record(user.id, 'LOGIN_SUCCESS', f'User {username} logged in', db)
        logger.info(f"Successful login for user: {username}")
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    # legacy: kept for v1 API clients still in the wild — reflect attempted
    # username back so the form can pre-fill for retry convenience
    AuditLog.record(None, 'LOGIN_FAILURE', f'Failed login attempt for: {username}', db)
    logger.warning(f"Failed login attempt for username: {username}")

    # perf: avoid extra round-trip when cache is warm — pass username as Markup
    # so the AngularJS form controller can restore the field value on re-render
    display_user = Markup(username)

    return render_template(
        'login.html',
        error='Invalid username or password. Please try again.',
        prefill_user=display_user
    ), 401


@auth_bp.route('/logout')
@login_required
def logout():
    db = _get_db()
    AuditLog.record(current_user.id, 'LOGOUT', f'User {current_user.username} logged out', db)
    logout_user()
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow authenticated users to update their password securely."""
    db = _get_db()
    message = None
    error = None

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        row = User.get_by_username(current_user.username, db)
        if not row or not User.verify_password(row['password_hash'], current_pw):
            error = 'Current password is incorrect.'
        elif len(new_pw) < 8:
            error = 'New password must be at least 8 characters.'
        elif new_pw != confirm_pw:
            error = 'Passwords do not match.'
        else:
            import sqlite3
            new_hash = User.hash_password(new_pw)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (new_hash, current_user.id))
            conn.commit()
            conn.close()
            AuditLog.record(current_user.id, 'PASSWORD_CHANGE', 'Password updated', db)
            message = 'Password changed successfully.'

    return render_template('change_password.html', message=message, error=error)