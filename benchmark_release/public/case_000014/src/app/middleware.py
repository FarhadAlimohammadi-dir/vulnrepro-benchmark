import functools
import logging
from flask import session, redirect, url_for, jsonify, request, g
from db import get_db

logger = logging.getLogger('promptforge.middleware')


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'authentication required'}), 401
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'forbidden'}), 403
            from flask import render_template
            return render_template('error.html', code=403, message='Admin access required'), 403
        return f(*args, **kwargs)
    return wrapper


def audit(action, detail=''):
    """Write a record to the audit log for the current session user."""
    user_id = session.get('user_id')
    if not user_id:
        return
    try:
        db = get_db()
        ip = request.remote_addr
        db.execute(
            'INSERT INTO audit_log (user_id, action, detail, ip_addr) VALUES (?,?,?,?)',
            (user_id, action, detail, ip)
        )
        db.commit()
        db.close()
    except Exception as exc:
        logger.warning('audit write failed: %s', exc)