import logging
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app import get_db
from app.models import User

logger = logging.getLogger("cloudpanel.admin")
admin_bp = Blueprint("admin", __name__)


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin():
        abort(403)


@admin_bp.route("/users")
@login_required
def list_users():
    require_admin()
    users = User.all_users()
    return render_template("admin_users.html", users=users, user=current_user)


@admin_bp.route("/audit")
@login_required
def audit_log():
    """Decoy: admin-only endpoint, properly checks role before returning logs."""
    require_admin()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT a.*, u.username FROM audit_log a "
            "LEFT JOIN users u ON u.id = a.user_id "
            "ORDER BY a.created_at DESC LIMIT 200"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
def change_role(user_id):
    """Decoy: role escalation endpoint — admin check is enforced."""
    require_admin()
    new_role = request.json.get("role") if request.is_json else None
    if new_role not in ("admin", "member"):
        return jsonify({"error": "invalid role"}), 400
    conn = get_db()
    try:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()
    finally:
        conn.close()
    logger.info("Admin %s changed role of user %d to %s", current_user.username, user_id, new_role)
    return jsonify({"ok": True})


@admin_bp.route("/stats")
@login_required
def stats():
    """Decoy: aggregate stats visible only to admins."""
    require_admin()
    conn = get_db()
    try:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    finally:
        conn.close()
    return jsonify({"users": user_count, "projects": project_count, "tasks": task_count})