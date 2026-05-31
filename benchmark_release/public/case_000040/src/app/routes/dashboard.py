import logging
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import get_db

logger = logging.getLogger("cloudpanel.dashboard")
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    conn = get_db()
    try:
        projects = conn.execute(
            "SELECT p.*, u.username as owner_name FROM projects p "
            "JOIN users u ON u.id = p.owner_id "
            "WHERE p.status = 'active' ORDER BY p.created_at DESC LIMIT 10"
        ).fetchall()
        task_counts = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
        ).fetchall()
        recent_audit = conn.execute(
            "SELECT a.*, u.username FROM audit_log a "
            "LEFT JOIN users u ON u.id = a.user_id "
            "ORDER BY a.created_at DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "dashboard.html",
        user=current_user,
        projects=[dict(p) for p in projects],
        task_counts=[dict(t) for t in task_counts],
        recent_audit=[dict(r) for r in recent_audit],
    )