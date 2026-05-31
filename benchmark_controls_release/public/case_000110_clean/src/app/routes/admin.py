import logging
import hmac
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from ..db import get_db

logger = logging.getLogger(__name__)
bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    if session.get("role") != "admin":
        return redirect(url_for("dashboard.home")), 403
    return None


def valid_csrf_request():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


@bp.route("/logs")
def audit_logs():
    check = require_admin()
    if check:
        return check

    db = get_db()
    page = request.args.get("page", 1, type=int)
    per_page = 25
    offset = (page - 1) * per_page

    logs = db.execute("""
        SELECT al.*, u.username
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset)).fetchall()

    total = db.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()["cnt"]

    return render_template(
        "admin_logs.html",
        logs=logs,
        page=page,
        per_page=per_page,
        total=total,
    )


@bp.route("/users")
def list_users():
    check = require_admin()
    if check:
        return check

    db = get_db()
    users = db.execute(
        "SELECT id, username, display_name, email, role, created_at, last_login FROM users ORDER BY id"
    ).fetchall()
    return render_template("admin_users.html", users=users)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
def update_user_role(user_id):
    check = require_admin()
    if check:
        return check

    new_role = request.form.get("role", "")
    if new_role not in ("user", "admin"):
        return jsonify({"error": "Invalid role"}), 400
    if not valid_csrf_request():
        return jsonify({"error": "Invalid request"}), 400

    db = get_db()
    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    db.commit()
    logger.info("Admin %s changed role of user_id=%s to %s", session["username"], user_id, new_role)
    return redirect(url_for("admin.list_users"))
