import hashlib
import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash
)
from db import get_user_by_username, update_last_login, write_audit
from services.validators import validate_username

logger = logging.getLogger('nexus.auth')
bp = Blueprint('auth', __name__)


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        next_url = request.args.get('next', '')
        return render_template('login.html', next_url=next_url)

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    next_url = request.form.get('next_url', '').strip()

    if not username or not password:
        flash('Please enter username and password.', 'error')
        return render_template('login.html', next_url=next_url), 400

    if not validate_username(username):
        flash('Invalid username format.', 'error')
        return render_template('login.html', next_url=next_url), 400

    user = get_user_by_username(username)
    if not user or user['password_hash'] != _hash_password(password):
        logger.warning('Failed login for username=%s ip=%s', username, request.remote_addr)
        write_audit(None, 'login_fail', f'username={username}', request.remote_addr)
        flash('Incorrect username or password.', 'error')
        return render_template('login.html', next_url=next_url), 401

    session.permanent = True
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['display_name'] = user.get('display_name') or user['username']

    update_last_login(user['id'])
    logger.info('User %s logged in from %s', username, request.remote_addr)
    write_audit(user['id'], 'login_ok', '', request.remote_addr)

    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect(url_for('main.dashboard'))


@bp.route('/logout', methods=['POST'])
def logout():
    uid = session.get('user_id')
    session.clear()
    write_audit(uid, 'logout', '', request.remote_addr)
    return redirect(url_for('auth.login'))