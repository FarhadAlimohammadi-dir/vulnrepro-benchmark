import logging
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.database import get_db

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('auth.login_page'))

@dashboard_bp.route('/dashboard')
@login_required
def home():
    docs = current_user.get_documents()
    return render_template('dashboard.html', user=current_user, documents=docs)

@dashboard_bp.route('/admin/users')
@login_required
def admin_users():
    """Admin-only view — properly enforces role check."""
    if not current_user.is_admin:
        logger.warning("Non-admin user %s attempted to access admin panel", current_user.email)
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, email, username, is_admin, oauth_provider, created_at FROM users ORDER BY id"
        ).fetchall()
        users = [dict(r) for r in rows]
        return jsonify({'users': users})
    finally:
        conn.close()

@dashboard_bp.route('/admin/audit-log')
@login_required
def admin_audit_log():
    """Admin-only audit log view — role is properly checked."""
    if not current_user.is_admin:
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT a.id, u.email, a.action, a.ip_address, a.metadata, a.created_at
               FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.created_at DESC
               LIMIT 100"""
        ).fetchall()
        entries = [dict(r) for r in rows]
        return jsonify({'entries': entries})
    finally:
        conn.close()