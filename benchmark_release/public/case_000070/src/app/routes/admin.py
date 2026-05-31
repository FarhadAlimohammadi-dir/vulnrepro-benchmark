import logging
import sqlite3
from flask import Blueprint, jsonify, current_app, request
from flask_login import login_required, current_user

admin_bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


def require_admin(f):
    """Decorator that enforces admin role."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/users", methods=["GET"])
@login_required
@require_admin
def list_users():
    db = current_app.config["DATABASE"]
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, role, created_at FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify({"users": [dict(r) for r in rows]})
    except Exception as e:
        logger.error("Admin list users error: %s", e)
        return jsonify({"error": "Internal error"}), 500


@admin_bp.route("/audit-log", methods=["GET"])
@login_required
@require_admin
def audit_log():
    """Return the most recent 200 audit events."""
    db = current_app.config["DATABASE"]
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """SELECT al.*, u.username FROM audit_log al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC LIMIT 200"""
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify({"events": [dict(r) for r in rows]})
    except Exception as e:
        logger.error("Audit log error: %s", e)
        return jsonify({"error": "Internal error"}), 500


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@login_required
@require_admin
def set_user_role(user_id):
    """Change a user's role. Requires admin and cannot demote self."""
    if user_id == current_user.id:
        return jsonify({"error": "Cannot change own role"}), 400

    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "")
    if new_role not in ("user", "admin"):
        return jsonify({"error": "Invalid role"}), 400

    try:
        conn = sqlite3.connect(db)
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Role update error: %s", e)
        return jsonify({"error": "Internal error"}), 500

    logger.info("Admin %s set user %s role to %s", current_user.username, user_id, new_role)
    return jsonify({"ok": True})


@admin_bp.route("/stats", methods=["GET"])
@login_required
@require_admin
def site_stats():
    db = current_app.config["DATABASE"]
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM users")
        user_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM documents")
        doc_count = cur.fetchone()["cnt"]
        conn.close()
        return jsonify({"users": user_count, "documents": doc_count})
    except Exception as e:
        logger.error("Stats error: %s", e)
        return jsonify({"error": "Internal error"}), 500