import logging
from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Employee, LeaveRequest, AuditLog

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)


def _get_db():
    return current_app.config['DATABASE']


@main_bp.route('/')
def index():
    return redirect(url_for('auth.login_page'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    db = _get_db()
    leave_requests = LeaveRequest.get_by_user(current_user.id, db)
    recent_logs = []
    if current_user.role == 'admin':
        recent_logs = AuditLog.get_recent(20, db)
    return render_template('dashboard.html', user=current_user,
                           leave_requests=leave_requests,
                           recent_logs=recent_logs)


@main_bp.route('/employees')
@login_required
def employees():
    db = _get_db()
    emp_list = Employee.get_all(db)
    return render_template('employees.html', employees=emp_list, user=current_user)


@main_bp.route('/leave/request', methods=['GET', 'POST'])
@login_required
def leave_request():
    db = _get_db()
    message = None
    error = None

    if request.method == 'POST':
        leave_type = request.form.get('leave_type', '')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        reason = request.form.get('reason', '')

        if not all([leave_type, start_date, end_date]):
            error = 'All fields are required.'
        else:
            rid = LeaveRequest.create(
                current_user.id, leave_type, start_date, end_date, reason, db
            )
            if rid:
                AuditLog.record(current_user.id, 'LEAVE_REQUEST',
                                f'Leave request #{rid} submitted', db)
                message = f'Leave request #{rid} submitted successfully.'
            else:
                error = 'Failed to submit leave request. Please try again.'

    return render_template('leave_request.html', message=message, error=error, user=current_user)


@main_bp.route('/profile')
@login_required
def profile():
    db = _get_db()
    leave_requests = LeaveRequest.get_by_user(current_user.id, db)
    return render_template('profile.html', user=current_user, leave_requests=leave_requests)


@main_bp.route('/announcements')
@login_required
def announcements():
    import sqlite3
    db = _get_db()
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        items = [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching announcements: {e}")
        items = []
    return render_template('announcements.html', announcements=items, user=current_user)