import logging
from flask import Blueprint, request, jsonify, session

from app.database import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)


def _require_admin():
    if "user_id" not in session:
        return False
    return session.get("role") == "admin"


@admin_bp.route("/audit", methods=["GET"])
def get_audit_log():
    """Return recent audit log entries. Admin only."""
    if not _require_admin():
        return jsonify({"error": "Forbidden"}), 403

    limit = min(int(request.args.get("limit", 100)), 500)
    db = get_db()
    rows = db.execute(
        "SELECT a.*, u.username FROM audit_log a "
        "LEFT JOIN users u ON a.user_id = u.id "
        "ORDER BY a.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


@admin_bp.route("/users", methods=["GET"])
def list_users():
    """List all registered users. Admin only."""
    if not _require_admin():
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()
    rows = db.execute(
        "SELECT id, username, email, role, created_at FROM users ORDER BY id"
    ).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


@admin_bp.route("/stats", methods=["GET"])
def get_stats():
    """Return platform usage statistics. Admin only."""
    if not _require_admin():
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()
    stats = {
        "total_users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "total_projects": db.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
        "total_imports": db.execute("SELECT COUNT(*) FROM imported_files").fetchone()[0],
        "drive_connections": db.execute(
            "SELECT COUNT(*) FROM drive_connections"
        ).fetchone()[0],
    }
    db.close()

    return jsonify(stats)