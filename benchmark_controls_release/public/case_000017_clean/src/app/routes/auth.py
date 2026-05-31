"""
Authentication routes: login, logout, registration.
"""
import re
from flask import Blueprint, request, render_template, redirect, url_for, session, g
import hashlib

bp = Blueprint('auth', __name__)


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def get_db():
    return g.db


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not re.match(r'^[a-zA-Z0-9_]{3,32}$', username):
            error = 'Invalid username format.'
        elif not password:
            error = 'Password is required.'
        else:
            db = get_db()
            row = db.execute(
                'SELECT * FROM users WHERE username=? AND password_hash=?',
                (username, hash_pw(password))
            ).fetchone()
            if row:
                session.clear()
                session['user_id'] = row['id']
                session['username'] = row['username']
                session['role'] = row['role']
                db.execute(
                    'UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?',
                    (row['id'],)
                )
                db.commit()
                return redirect(url_for('main.index'))
            else:
                error = 'Invalid username or password.'
    return render_template('login.html', error=error)


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))