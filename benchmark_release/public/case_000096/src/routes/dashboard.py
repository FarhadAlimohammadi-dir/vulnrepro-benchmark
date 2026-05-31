import logging
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    return redirect(url_for('auth.login_page'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)