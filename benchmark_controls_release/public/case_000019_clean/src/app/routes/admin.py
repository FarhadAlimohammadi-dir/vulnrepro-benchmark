import logging
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash
)
from db import get_audit_log, get_all_users, write_audit

logger = logging.getLogger('nexus.admin')
bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/')
@admin_required
def admin_dashboard():
    users, total_users = get_all_users(limit=10)
    logs, total_logs = get_audit_log(limit=20)
    return render_template(
        'admin/dashboard.html',
        username=session['username'],
        users=users,
        total_users=total_users,
        logs=logs,
        total_logs=total_logs,
    )


@bp.route('/users')
@admin_required
def admin_users():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    users, total = get_all_users(limit=per_page, offset=offset)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'admin/users.html',
        username=session['username'],
        users=users,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route('/audit')
@admin_required
def admin_audit():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 50
    offset = (page - 1) * per_page
    logs, total = get_audit_log(limit=per_page, offset=offset)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        'admin/audit.html',
        username=session['username'],
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )