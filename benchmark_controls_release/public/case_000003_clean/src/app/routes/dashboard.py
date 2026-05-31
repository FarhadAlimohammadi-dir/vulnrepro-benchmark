import logging
from flask import Blueprint, render_template, g, request
from routes.auth import login_required
from database import get_workspaces_for_user, get_audit_log, get_notifications

logger = logging.getLogger('codenest.dashboard')
bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    page = int(request.args.get('page', 1))
    workspaces, total = get_workspaces_for_user(g.user['id'], page=page, per_page=10)
    notifications = get_notifications(g.user['id'], unread_only=True)
    total_pages = max(1, (total + 9) // 10)
    return render_template(
        'dashboard.html',
        user=g.user,
        workspaces=workspaces,
        notifications=notifications,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route('/activity')
@login_required
def activity():
    events = get_audit_log(limit=100, user_id=g.user['id'])
    return render_template('activity.html', user=g.user, events=events)