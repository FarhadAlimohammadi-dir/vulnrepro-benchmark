import functools
from flask import session, redirect, url_for, abort, request


def current_user():
    return session.get('user')


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        u = current_user()
        if not u:
            return redirect(url_for('login_page', next=request.path))
        if u.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated