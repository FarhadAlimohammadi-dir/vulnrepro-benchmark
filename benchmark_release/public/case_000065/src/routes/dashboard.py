import logging
from flask import Blueprint, render_template, session, redirect, url_for
import database

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect('/login')

    user_id = session['user_id']

    campaigns = database.query_db(
        "SELECT id, name, status, budget FROM campaigns WHERE owner_id = ? LIMIT 10",
        (user_id,)
    )

    return render_template('dashboard.html',
                           username=session.get('username'),
                           campaigns=[dict(c) for c in campaigns])


@dashboard_bp.route('/login')
def login_page():
    return render_template('login.html')