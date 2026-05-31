import logging
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify
from routes.auth import login_required
from database import (
    get_user_by_id, update_user_profile, write_audit,
    get_notifications, mark_notifications_read, get_audit_log
)

logger = logging.getLogger('codenest.profile')
bp = Blueprint('profile', __name__, url_prefix='/profile')


@bp.route('/')
@login_required
def index():
    events = get_audit_log(limit=20, user_id=g.user['id'])
    notifications = get_notifications(g.user['id'])
    return render_template('profile.html', user=g.user, events=events, notifications=notifications)


@bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    error = None
    success = None
    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()[:500]
        avatar_url = request.form.get('avatar_url', '').strip()[:300]
        if avatar_url and not (avatar_url.startswith('http://') or avatar_url.startswith('https://')):
            error = 'Avatar URL must be an http(s) URL'
        else:
            update_user_profile(g.user['id'], bio, avatar_url)
            write_audit(g.user['id'], 'profile_updated', ip=request.remote_addr)
            success = 'Profile updated successfully'
            from database import get_user_by_id
            g.user = get_user_by_id(g.user['id'])
    return render_template('profile_edit.html', user=g.user, error=error, success=success)


@bp.route('/notifications/read', methods=['POST'])
@login_required
def mark_read():
    mark_notifications_read(g.user['id'])
    return jsonify({'ok': True})