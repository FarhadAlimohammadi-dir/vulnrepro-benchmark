import logging
import functools
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, g
)
from database import get_user_by_username, verify_password, update_last_login, write_audit

logger = logging.getLogger('codenest.auth')
bp = Blueprint('auth', __name__)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        from database import get_user_by_id
        g.user = get_user_by_id(user_id)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('auth.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            if g.user['role'] not in roles:
                return render_template(
                    'error.html', code=403,
                    message='Access denied — insufficient permissions'
                ), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = get_user_by_username(username)
        if user is None or not verify_password(user, password):
            error = 'Invalid username or password'
            logger.info('Failed login attempt for user: %r', username)
        else:
            session.clear()
            session['user_id'] = user['id']
            update_last_login(user['id'])
            write_audit(user['id'], 'login', ip=request.remote_addr)
            logger.info('User %r authenticated', username)
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('dashboard.index'))

    return render_template('login.html', error=error)


@bp.route('/logout', methods=['POST'])
def logout():
    if g.user:
        write_audit(g.user['id'], 'logout', ip=request.remote_addr)
        logger.info('User %r logged out', g.user['username'])
    session.clear()
    return redirect(url_for('auth.login'))
