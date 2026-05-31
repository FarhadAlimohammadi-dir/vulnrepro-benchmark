from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('index.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('index.html')


@pages_bp.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('pages.dashboard'))
    return render_template('index.html')


@pages_bp.route('/health')
def health():
    return {'status': 'ok', 'service': 'taskflow'}