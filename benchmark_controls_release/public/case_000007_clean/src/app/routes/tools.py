import json
import logging
import re
import sqlite3
from flask import Blueprint, request, jsonify, session

from db import get_connection
from services.tool_service import validate_tool_name, execute_handler
from services.audit_service import record as audit
from services.pagination import paginate
from middleware import register_middleware

logger = logging.getLogger("toolforge.tools")
tools_bp = Blueprint("tools", __name__)

KNOWN_HANDLERS = {"read_file", "http_fetch", "template_render"}


def require_login(f):
    from functools import wraps
    @wraps(f)
    def _inner(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "authentication required"}), 401
        return f(*args, **kwargs)
    return _inner


# ── list ─────────────────────────────────────────────────────────────────────

@tools_bp.route("", methods=["GET"])
@require_login
def list_tools():
    page = max(1, int(request.args.get("page", 1)))
    tag_filter = request.args.get("tag", "").strip()
    search = request.args.get("q", "").strip().lower()

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name,description,handler,owner,tags,invoke_count,created_at "
            "FROM tools WHERE is_active=1 ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    tools = [dict(r) for r in rows]

    if tag_filter:
        tools = [t for t in tools if tag_filter in (t.get("tags") or "")]
    if search:
        tools = [t for t in tools if search in t["name"].lower() or search in (t["description"] or "").lower()]

    paged = paginate(tools, page, per_page=15)
    return jsonify(paged)


# ── register ──────────────────────────────────────────────────────────────────

@tools_bp.route("/register", methods=["POST"])
@require_login
def register_tool():
    """Register a new automation tool with a named handler."""
    data = request.get_json(force=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    handler = str(data.get("handler", "")).strip()
    config = data.get("config", {})
    tags = str(data.get("tags", "")).strip()

    err = validate_tool_name(name)
    if err:
        return jsonify({"error": err}), 400
    if not handler:
        return jsonify({"error": "handler is required"}), 400
    if handler not in KNOWN_HANDLERS:
        return jsonify({"error": "handler is not supported"}), 400
    if len(description) > 512:
        return jsonify({"error": "description too long (max 512 chars)"}), 400
    if handler in {"template_render", "read_file"} and session.get("role") != "admin":
        return jsonify({"error": "only administrators may register this handler"}), 403

    conn = get_connection()
    try:
        try:
            conn.execute(
                "INSERT INTO tools(name,description,handler,config,owner,tags) VALUES(?,?,?,?,?,?)",
                (name, description, handler, json.dumps(config), session["username"], tags)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            existing = conn.execute("SELECT owner FROM tools WHERE name=?", (name,)).fetchone()
            if existing and (existing["owner"] == session["username"] or session["role"] == "admin"):
                conn.execute(
                    "UPDATE tools SET description=?,handler=?,config=?,tags=?,updated_at=CURRENT_TIMESTAMP "
                    "WHERE name=?",
                    (description, handler, json.dumps(config), tags, name)
                )
                conn.commit()
                audit(conn, session["username"], "tool.updated", name, f"handler={handler}")
                conn.commit()
                return jsonify({"ok": True, "registered": name, "updated": True})
            else:
                return jsonify({"error": "tool name already taken by another user"}), 409

        audit(conn, session["username"], "tool.created", name, f"handler={handler}")
        conn.commit()
    finally:
        conn.close()

    logger.info("Tool '%s' registered by '%s' with handler '%s'", name, session["username"], handler)
    return jsonify({"ok": True, "registered": name})


# ── validate ──────────────────────────────────────────────────────────────────

@tools_bp.route("/validate", methods=["GET"])
@require_login
def validate_tool():
    """Check availability of a tool name and whether the handler type is known."""
    name = request.args.get("name", "").strip()
    handler = request.args.get("handler", "").strip()

    name_err = validate_tool_name(name) if name else None
    conn = get_connection()
    try:
        taken = conn.execute("SELECT id FROM tools WHERE name=?", (name,)).fetchone()
    finally:
        conn.close()

    return jsonify({
        "name_available": not bool(taken),
        "name_valid": name_err is None,
        "name_error": name_err,
        "handler_recognized": handler in KNOWN_HANDLERS,
    })


# ── clone ─────────────────────────────────────────────────────────────────────

@tools_bp.route("/clone", methods=["POST"])
@require_login
def clone_tool():
    """Duplicate a tool under a new name for iteration or personalisation."""
    data = request.get_json(force=True) or {}
    source = str(data.get("source", "")).strip()
    new_name = str(data.get("new_name", "")).strip()

    err = validate_tool_name(new_name)
    if err:
        return jsonify({"error": err}), 400

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tools WHERE name=?", (source,)).fetchone()
        if not row:
            return jsonify({"error": "source tool not found"}), 404
        if row["owner"] != session["username"] and session.get("role") != "admin":
            return jsonify({"error": "source tool not found"}), 404
        try:
            conn.execute(
                "INSERT INTO tools(name,description,handler,config,owner,tags) VALUES(?,?,?,?,?,?)",
                (new_name, row["description"], row["handler"], row["config"],
                 session["username"], row["tags"])
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "new name already taken"}), 409

        audit(conn, session["username"], "tool.cloned", new_name, f"source={source}")
        conn.commit()
    finally:
        conn.close()

    logger.info("Tool '%s' cloned from '%s' by '%s'", new_name, source, session["username"])
    return jsonify({"ok": True, "cloned_as": new_name, "source": source})


# ── delete ────────────────────────────────────────────────────────────────────

@tools_bp.route("/<tool_name>", methods=["DELETE"])
@require_login
def delete_tool(tool_name):
    """Soft-delete a tool (sets is_active=0). Admins can delete any tool."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT owner FROM tools WHERE name=?", (tool_name,)).fetchone()
        if not row:
            return jsonify({"error": "tool not found"}), 404
        if row["owner"] != session["username"] and session["role"] != "admin":
            return jsonify({"error": "not authorised to delete this tool"}), 403
        conn.execute("UPDATE tools SET is_active=0 WHERE name=?", (tool_name,))
        conn.commit()
        audit(conn, session["username"], "tool.deleted", tool_name)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "deleted": tool_name})


# ── invoke ────────────────────────────────────────────────────────────────────

@tools_bp.route("/invoke", methods=["POST"])
@require_login
def invoke_tool():
    """Dispatch a registered tool by its configured handler type."""
    data = request.get_json(force=True) or {}
    name = str(data.get("name", "")).strip()
    args = data.get("args", {})

    if not name:
        return jsonify({"error": "name is required"}), 400

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tools WHERE name=? AND is_active=1", (name,)).fetchone()
        if not row:
            return jsonify({"error": "tool not found or inactive"}), 404
        if row["owner"] != session["username"] and session.get("role") != "admin":
            return jsonify({"error": "tool not found or inactive"}), 404

        handler = row["handler"]
        stored_config = json.loads(row["config"] or "{}")

        result, error, duration_ms = execute_handler(handler, stored_config, args)

        snippet = str(result)[:300] if result else (str(error)[:300] if error else "")
        status = "error" if error else "ok"

        conn.execute(
            "INSERT INTO invocations(tool_name,invoked_by,args_snapshot,result_snippet,duration_ms,status) "
            "VALUES(?,?,?,?,?,?)",
            (name, session["username"], json.dumps(args)[:500], snippet, duration_ms, status)
        )
        conn.execute(
            "UPDATE tools SET invoke_count=invoke_count+1, updated_at=CURRENT_TIMESTAMP WHERE name=?",
            (name,)
        )
        conn.commit()

        audit(conn, session["username"], "tool.invoked", name,
              f"handler={handler} status={status} ms={duration_ms}")
        conn.commit()
    finally:
        conn.close()

    if error:
        return jsonify({"ok": False, "handler": handler, "error": error}), 400

    logger.info("Tool '%s' invoked by '%s' (%dms)", name, session["username"], duration_ms)
    return jsonify({"ok": True, "handler": handler, "result": result})


# ── invocation history ────────────────────────────────────────────────────────

@tools_bp.route("/invocations", methods=["GET"])
@require_login
def list_invocations():
    page = max(1, int(request.args.get("page", 1)))
    tool_filter = request.args.get("tool", "").strip()
    status_filter = request.args.get("status", "").strip()

    conn = get_connection()
    try:
        if session.get("role") == "admin":
            rows = conn.execute(
                "SELECT tool_name,invoked_by,result_snippet,duration_ms,status,created_at "
                "FROM invocations ORDER BY id DESC LIMIT 500"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT tool_name,invoked_by,result_snippet,duration_ms,status,created_at "
                "FROM invocations WHERE invoked_by=? ORDER BY id DESC LIMIT 500",
                (session["username"],),
            ).fetchall()
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    if tool_filter:
        items = [i for i in items if i["tool_name"] == tool_filter]
    if status_filter:
        items = [i for i in items if i["status"] == status_filter]

    paged = paginate(items, page, per_page=25)
    return jsonify(paged)
