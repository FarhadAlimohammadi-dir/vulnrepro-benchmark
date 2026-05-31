import logging
from flask import Blueprint, request, session, redirect, url_for, render_template, g
from db import get_db
import middleware

logger = logging.getLogger('promptforge.auth')
bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            error = 'Username and password are required.'
        else:
            db = get_db()
            row = db.execute(
                'SELECT id, username, role FROM users WHERE username=? AND password=?',
                (username, password)
            ).fetchone()
            db.close()
            if not row:
                logger.warning('failed login attempt for username=%r ip=%s',
                               username, request.remote_addr)
                error = 'Invalid credentials. Please try again.'
            else:
                session['user_id'] = row['id']
                session['username'] = row['username']
                session['role'] = row['role']
                # Update last_login
                db2 = get_db()
                db2.execute(
                    "UPDATE users SET last_login=datetime('now') WHERE id=?",
                    (row['id'],)
                )
                db2.commit()
                db2.close()
                middleware.audit('login', 'user logged in')
                logger.info('user %r logged in', username)
                next_url = request.args.get('next') or url_for('dashboard')
                return redirect(next_url)
    return render_template('login.html', error=error)


@bp.route('/logout')
def logout():
    if session.get('user_id'):
        middleware.audit('logout', 'user logged out')
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/profile')
@middleware.login_required
def profile():
    db = get_db()
    row = db.execute(
        'SELECT username, email, full_name, bio, role, created_at, last_login FROM users WHERE id=?',
        (g.user_id,)
    ).fetchone()
    db.close()
    return render_template('profile.html', user=row)


@bp.route('/profile/edit', methods=['GET', 'POST'])
@middleware.login_required
def edit_profile():
    db = get_db()
    row = db.execute(
        'SELECT * FROM users WHERE id=?', (g.user_id,)
    ).fetchone()
    error = None
    success = None
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()[:100]
        email = request.form.get('email', '').strip()[:200]
        bio = request.form.get('bio', '').strip()[:500]
        db.execute(
            'UPDATE users SET full_name=?, email=?, bio=? WHERE id=?',
            (full_name, email, bio, g.user_id)
        )
        db.commit()
        middleware.audit('profile_update', 'profile fields updated')
        success = 'Profile updated successfully.'
        row = db.execute('SELECT * FROM users WHERE id=?', (g.user_id,)).fetchone()
    db.close()
    return render_template('edit_profile.html', user=row, error=error, success=success)