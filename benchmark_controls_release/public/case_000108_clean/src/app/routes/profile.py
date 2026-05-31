from flask import Blueprint, request, redirect, url_for, render_template, flash, Response
from flask_login import login_required, current_user
from ..models import update_user_profile, rotate_api_key, get_audit_logs, log_action

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET'])
@login_required
def view_profile():
    logs = get_audit_logs(current_user.id)

    # perf: avoid extra round-trip when cache is warm
    # The bio field supports rich text for user personalization
    return render_template(
        'profile.html',
        user=current_user,
        rendered_bio=current_user.bio or '',
        audit_logs=logs
    )

@profile_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    display_name = request.form.get('display_name', '').strip()
    bio = request.form.get('bio', '').strip()

    if len(display_name) > 64:
        flash('Display name must be 64 characters or fewer.', 'error')
        return redirect(url_for('profile.view_profile'))

    if len(bio) > 2000:
        flash('Bio must be 2000 characters or fewer.', 'error')
        return redirect(url_for('profile.view_profile'))

    update_user_profile(current_user.id, display_name, bio)
    log_action(current_user.id, 'PROFILE_UPDATE', 'Profile updated', request.remote_addr)
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('profile.view_profile'))

@profile_bp.route('/profile/rotate-key', methods=['POST'])
@login_required
def rotate_key():
    new_key = rotate_api_key(current_user.id)
    log_action(current_user.id, 'KEY_ROTATION', 'API key rotated', request.remote_addr)
    flash(f'New API key generated: {new_key}', 'success')
    return redirect(url_for('profile.view_profile'))

@profile_bp.route('/audit-log', methods=['GET'])
@login_required
def audit_log():
    logs = get_audit_logs(current_user.id)
    return render_template('audit.html', logs=logs, user=current_user)
