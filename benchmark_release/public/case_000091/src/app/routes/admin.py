import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..db import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/audit", methods=["GET"])
@login_required
@require_admin
def audit_log():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    offset = (page - 1) * per_page
    action_filter = request.args.get("action", "")

    db = get_db()
    try:
        query = """SELECT a.id, a.action, a.resource_type, a.resource_id,
                          a.ip_address, a.created_at, u.username
                   FROM audit_logs a
                   LEFT JOIN users u ON a.user_id = u.id"""
        params = []
        if action_filter:
            query += " WHERE a.action = ?"
            params.append(action_filter)
        query += " ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        rows = db.execute(query, params).fetchall()
    finally:
        db.close()

    return jsonify({"logs": [dict(r) for r in rows], "page": page}), 200


@admin_bp.route("/users", methods=["GET"])
@login_required
@require_admin
def list_users():
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, username, email, role, created_at FROM users ORDER BY created_at"
        ).fetchall()
    finally:
        db.close()
    return jsonify({"users": [dict(r) for r in rows]}), 200


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@login_required
@require_admin
def update_user_role(user_id):
    data = request.get_json(silent=True) or {}
    new_role = data.get("role", "").strip()
    if new_role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role. Must be admin, editor, or viewer"}), 400

    db = get_db()
    try:
        row = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return jsonify({"error": "User not found"}), 404
        db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, 'UPDATE_USER_ROLE', 'user', ?, ?)",
            (current_user.id, user_id, request.remote_addr)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({"message": f"User {user_id} role updated to {new_role}"}), 200


@admin_bp.route("/stats", methods=["GET"])
@login_required
@require_admin
def stats():
    db = get_db()
    try:
        doc_count = db.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
        user_count = db.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        public_count = db.execute("SELECT COUNT(*) as cnt FROM documents WHERE is_public=1").fetchone()["cnt"]
        recent_logins = db.execute(
            """SELECT u.username, a.created_at, a.ip_address
               FROM audit_logs a JOIN users u ON a.user_id = u.id
               WHERE a.action = 'LOGIN' ORDER BY a.created_at DESC LIMIT 10"""
        ).fetchall()
    finally:
        db.close()

    return jsonify({
        "document_count": doc_count,
        "user_count": user_count,
        "public_document_count": public_count,
        "recent_logins": [dict(r) for r in recent_logins],
    }), 200