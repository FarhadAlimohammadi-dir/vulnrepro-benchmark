import logging
from flask import Blueprint, jsonify, request, current_app, render_template
from flask_login import login_required, current_user
from functools import wraps
from ..models import get_db, log_audit

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def list_users():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    rows = conn.execute(
        "SELECT id, username, email, role, display_name, oidc_sub, created_at FROM users ORDER BY created_at"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@login_required
@admin_required
def update_user_role(user_id):
    data = request.get_json(silent=True) or {}
    new_role = data.get("role")

    if new_role not in ("member", "admin"):
        return jsonify({"error": "Role must be 'member' or 'admin'"}), 400

    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    result = conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        return jsonify({"error": "User not found"}), 404

    log_audit(db_path, current_user.id, "admin.role_change", "user", user_id,
              f"Role set to {new_role}", request.remote_addr)
    return jsonify({"status": "ok"})


@admin_bp.route("/audit-log", methods=["GET"])
@login_required
@admin_required
def get_audit_log():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, int(request.args.get("per_page", 20)))
    offset = (page - 1) * per_page

    rows = conn.execute(
        "SELECT a.*, u.username FROM audit_log a "
        "LEFT JOIN users u ON a.user_id = u.id "
        "ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()

    return jsonify({
        "entries": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.route("/stats", methods=["GET"])
@login_required
@admin_required
def get_stats():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    oidc_user_count = conn.execute("SELECT COUNT(*) FROM users WHERE oidc_sub IS NOT NULL").fetchone()[0]

    recent_logins = conn.execute(
        "SELECT u.username, a.created_at, a.ip_address FROM audit_log a "
        "JOIN users u ON a.user_id = u.id WHERE a.action='auth.login' "
        "ORDER BY a.created_at DESC LIMIT 5"
    ).fetchall()

    conn.close()
    return jsonify({
        "users": user_count,
        "projects": project_count,
        "tasks": task_count,
        "oidc_users": oidc_user_count,
        "recent_logins": [dict(r) for r in recent_logins],
    })