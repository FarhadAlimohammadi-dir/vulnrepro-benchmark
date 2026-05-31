import logging
import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
profile_bp = Blueprint('profile', __name__)


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


@profile_bp.route('/profile')
@login_required
def view_profile():
    db = get_db()
    user = db.execute(
        'SELECT id, username, email, role, bio, created_at FROM users WHERE id = ?',
        (current_user.id,)
    ).fetchone()
    return render_template('profile.html', user=user)


@profile_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    db = get_db()
    bio = request.form.get('bio', '').strip()
    email = request.form.get('email', '').strip()

    if len(bio) > 500:
        flash('Bio must be under 500 characters.', 'error')
        return redirect(url_for('profile.view_profile'))

    if email and '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('profile.view_profile'))

    db.execute(
        'UPDATE users SET bio = ?, email = ? WHERE id = ?',
        (bio, email, current_user.id)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'profile.update', 'Profile updated', request.remote_addr)
    )
    db.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('profile.view_profile'))


@profile_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    user_row = db.execute(
        'SELECT password_hash FROM users WHERE id = ?', (current_user.id,)
    ).fetchone()

    if not bcrypt.checkpw(current_pw.encode('utf-8'), user_row['password_hash'].encode('utf-8')):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile.view_profile'))

    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile.view_profile'))

    if len(new_pw) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('profile.view_profile'))

    new_hash = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, current_user.id))
    db.execute(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'profile.password_change', 'Password changed', request.remote_addr)
    )
    db.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('profile.view_profile'))