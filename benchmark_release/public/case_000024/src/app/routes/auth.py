import hashlib
from urllib.parse import urlparse

from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from db import get_db
from services.audit_service import log_action

bp = Blueprint('auth', __name__)


def _safe_next_url(candidate: str) -> str:
    if not candidate:
        return url_for('main.dashboard')
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc or not candidate.startswith('/'):
        return url_for('main.dashboard')
    return candidate


@bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        next_url  = _safe_next_url(request.form.get('next') or request.args.get('next') or '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')

        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        user = db.execute(
            'SELECT id, username, role FROM users WHERE username=? AND password_hash=?',
            (username, pw_hash)
        ).fetchone()

        if user:
            session.clear()
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['role']     = user['role']
            log_action(user['id'], 'login', ip=request.remote_addr)
            return redirect(next_url)

        log_action(None, 'login_failed', detail=username, ip=request.remote_addr)
        flash('Invalid username or password.', 'error')
    return render_template('login.html', next_url=_safe_next_url(request.args.get('next', '')))


@bp.route('/logout')
def logout():
    uid = session.get('user_id')
    session.clear()
    if uid:
        log_action(uid, 'logout', ip=request.remote_addr)
    return redirect(url_for('auth.login_page'))
