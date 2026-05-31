import sqlite3
import logging
from flask import Blueprint, render_template, abort, request, jsonify
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
DATABASE = "notes.db"


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/audit", methods=["GET"])
@login_required
@require_admin
def audit_log():
    """Display recent audit events for compliance review."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT a.id, u.username, a.action, a.target_id, a.ip_address, a.created_at
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 500
        """).fetchall()
    finally:
        db.close()
    return render_template("audit.html", events=rows)


@admin_bp.route("/users", methods=["GET"])
@login_required
@require_admin
def list_users():
    """Return user roster for admin dashboard."""
    db = get_db()
    try:
        users = db.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    return jsonify({"users": [dict(u) for u in users]})


@admin_bp.route("/stats", methods=["GET"])
@login_required
@require_admin
def stats():
    """Aggregate statistics for operational dashboard."""
    db = get_db()
    try:
        note_count = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        public_count = db.execute("SELECT COUNT(*) FROM notes WHERE is_public=1").fetchone()[0]
    finally:
        db.close()
    return jsonify({
        "total_notes": note_count,
        "total_users": user_count,
        "public_notes": public_count,
    })