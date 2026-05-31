import logging
from flask import Blueprint, render_template, session, redirect, url_for

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


def require_login():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return None


@web_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('auth.login_page'))


@web_bp.route('/dashboard')
def dashboard():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('dashboard.html', username=session.get('username'))


@web_bp.route('/health')
def health():
    return {'status': 'ok', 'service': 'projecthub'}, 200