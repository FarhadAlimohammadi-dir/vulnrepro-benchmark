import logging
from flask import Blueprint, request, jsonify, session, render_template

from db import get_connection
from services.audit_service import record as audit
from services.pagination import paginate

logger = logging.getLogger("toolforge.admin")
admin_bp = Blueprint("admin", __name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def _inner(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "authentication required"}), 401
        if session.get("role") != "admin":
            return jsonify({"error": "admin privileges required"}), 403
        return f(*args, **kwargs)
    return _inner


@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    page = max(1, int(request.args.get("page", 1)))
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id,username,role,email,display_name,created_at,last_login FROM users ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    users = [dict(r) for r in rows]
    paged = paginate(users, page, per_page=20)
    return jsonify(paged)


@admin_bp.route("/users/<int:user_id>", methods=["PATCH"])
@require_admin
def update_user(user_id):
    data = request.get_json(force=True) or {}
    allowed_fields = {"role", "email", "display_name"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return jsonify({"error": "no valid fields provided"}), 400

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)
        conn.commit()
        audit(conn, session["username"], "user.updated", str(user_id),
              f"fields={list(updates.keys())}")
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "updated_fields": list(updates.keys())})


@admin_bp.route("/audit", methods=["GET"])
@require_admin
def audit_log():
    page = max(1, int(request.args.get("page", 1)))
    actor_filter = request.args.get("actor", "").strip()
    action_filter = request.args.get("action", "").strip()

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT actor,action,target,detail,ip_addr,created_at "
            "FROM audit_log ORDER BY id DESC LIMIT 1000"
        ).fetchall()
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    if actor_filter:
        items = [i for i in items if i["actor"] == actor_filter]
    if action_filter:
        items = [i for i in items if i["action"] == action_filter]

    paged = paginate(items, page, per_page=30)
    return jsonify(paged)


@admin_bp.route("/stats", methods=["GET"])
@require_admin
def stats():
    conn = get_connection()
    try:
        tool_count   = conn.execute("SELECT COUNT(*) FROM tools WHERE is_active=1").fetchone()[0]
        user_count   = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        invoke_count = conn.execute("SELECT COUNT(*) FROM invocations").fetchone()[0]
        top_tools    = conn.execute(
            "SELECT name, invoke_count FROM tools ORDER BY invoke_count DESC LIMIT 5"
        ).fetchall()
        recent_errors = conn.execute(
            "SELECT tool_name, created_at FROM invocations WHERE status='error' ORDER BY id DESC LIMIT 10"
        ).fetchall()
    finally:
        conn.close()

    return jsonify({
        "tool_count": tool_count,
        "user_count": user_count,
        "invoke_count": invoke_count,
        "top_tools": [dict(r) for r in top_tools],
        "recent_errors": [dict(r) for r in recent_errors],
    })


@admin_bp.route("/tools", methods=["GET"])
@require_admin
def all_tools():
    page = max(1, int(request.args.get("page", 1)))
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id,name,description,handler,owner,tags,is_active,invoke_count,created_at "
            "FROM tools ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    tools = [dict(r) for r in rows]
    paged = paginate(tools, page, per_page=20)
    return jsonify(paged)


@admin_bp.route("/tools/<tool_name>/toggle", methods=["POST"])
@require_admin
def toggle_tool(tool_name):
    conn = get_connection()
    try:
        row = conn.execute("SELECT is_active FROM tools WHERE name=?", (tool_name,)).fetchone()
        if not row:
            return jsonify({"error": "tool not found"}), 404
        new_state = 0 if row["is_active"] else 1
        conn.execute("UPDATE tools SET is_active=? WHERE name=?", (new_state, tool_name))
        conn.commit()
        audit(conn, session["username"], "tool.toggled", tool_name, f"is_active={new_state}")
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "is_active": bool(new_state)})