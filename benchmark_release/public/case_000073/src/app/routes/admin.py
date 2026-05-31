import logging
from flask import Blueprint, jsonify, request
import flask_login
from app.database import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _require_admin():
    if not flask_login.current_user.is_authenticated or not flask_login.current_user.is_admin():
        return jsonify({"error": "Admin access required"}), 403
    return None


@admin_bp.route("/users", methods=["GET"])
@flask_login.login_required
def list_users():
    err = _require_admin()
    if err:
        return err
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, username, email, role, created_at FROM users ORDER BY id"
        ).fetchall()
        return jsonify({"users": [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@admin_bp.route("/audit-log", methods=["GET"])
@flask_login.login_required
def get_audit_log():
    err = _require_admin()
    if err:
        return err

    limit = min(int(request.args.get("limit", 50)), 200)
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT al.id, u.username, al.action, al.entity_type, al.entity_id,
                      al.detail, al.ip_address, al.created_at
               FROM audit_log al
               LEFT JOIN users u ON al.user_id = u.id
               ORDER BY al.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return jsonify({"audit_log": [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@admin_bp.route("/properties", methods=["GET"])
@flask_login.login_required
def list_all_properties():
    err = _require_admin()
    if err:
        return err
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT p.*, u.username as owner_username
               FROM properties p
               JOIN users u ON p.owner_id = u.id
               ORDER BY p.created_at DESC"""
        ).fetchall()
        return jsonify({"properties": [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@admin_bp.route("/stats", methods=["GET"])
@flask_login.login_required
def global_stats():
    err = _require_admin()
    if err:
        return err
    conn = get_db()
    try:
        stats = {}
        stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats["total_properties"] = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        stats["total_reports"] = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        stats["total_webhooks"] = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
        bw = conn.execute("SELECT SUM(bandwidth_gb) FROM reports").fetchone()[0] or 0
        stats["total_bandwidth_gb"] = round(bw, 2)
        return jsonify(stats), 200
    finally:
        conn.close()