import logging
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user, login_user, logout_user
from ..models import User

logger = logging.getLogger(__name__)
web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('web.login_page'))


@web_bp.route('/login')
def login_page():
    return render_template('login.html')


@web_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


@web_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('web.login_page'))