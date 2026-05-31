import logging
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify

from db import get_connection
from services.pagination import paginate

logger = logging.getLogger("toolforge.ui")
ui_bp = Blueprint("ui", __name__)


def login_required(f):
    from functools import wraps
    @wraps(f)
    def _inner(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("ui.login_page"))
        return f(*args, **kwargs)
    return _inner


@ui_bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("ui.dashboard"))
    return redirect(url_for("ui.login_page"))


@ui_bp.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("ui.dashboard"))
    return render_template("login.html")


@ui_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    try:
        tools = conn.execute(
            "SELECT name,description,handler,owner,invoke_count FROM tools "
            "WHERE is_active=1 ORDER BY invoke_count DESC LIMIT 10"
        ).fetchall()
        recent = conn.execute(
            "SELECT tool_name,invoked_by,status,created_at FROM invocations "
            "ORDER BY id DESC LIMIT 8"
        ).fetchall()
        counts = conn.execute(
            "SELECT (SELECT COUNT(*) FROM tools WHERE is_active=1) as tc, "
            "(SELECT COUNT(*) FROM invocations) as ic, "
            "(SELECT COUNT(*) FROM users) as uc"
        ).fetchone()
    finally:
        conn.close()

    return render_template(
        "dashboard.html",
        tools=[dict(t) for t in tools],
        recent=[dict(r) for r in recent],
        counts=dict(counts),
    )


@ui_bp.route("/tools")
@login_required
def tools_page():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    page = max(1, int(request.args.get("page", 1)))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name,description,handler,owner,tags,invoke_count,created_at "
            "FROM tools WHERE is_active=1 ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    tools = [dict(r) for r in rows]
    if q:
        tools = [t for t in tools if q.lower() in t["name"].lower() or q.lower() in (t["description"] or "").lower()]
    if tag:
        tools = [t for t in tools if tag in (t["tags"] or "")]

    paged = paginate(tools, page, per_page=12)
    return render_template("tools.html", paged=paged, q=q, tag=tag)


@ui_bp.route("/tools/<tool_name>")
@login_required
def tool_detail(tool_name):
    conn = get_connection()
    try:
        tool = conn.execute("SELECT * FROM tools WHERE name=?", (tool_name,)).fetchone()
        if not tool:
            flash("Tool not found.", "danger")
            return redirect(url_for("ui.tools_page"))
        if tool["owner"] != session["username"] and session.get("role") != "admin":
            flash("Tool not found.", "danger")
            return redirect(url_for("ui.tools_page"))
        history = conn.execute(
            "SELECT invoked_by,result_snippet,duration_ms,status,created_at "
            "FROM invocations WHERE tool_name=? ORDER BY id DESC LIMIT 20",
            (tool_name,)
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "tool_detail.html",
        tool=dict(tool),
        history=[dict(h) for h in history]
    )


@ui_bp.route("/profile")
@login_required
def profile():
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT id,username,role,email,display_name,created_at,last_login "
            "FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        my_tools = conn.execute(
            "SELECT name,handler,invoke_count,is_active,created_at FROM tools WHERE owner=? ORDER BY created_at DESC",
            (session["username"],)
        ).fetchall()
        my_invocations = conn.execute(
            "SELECT tool_name,status,created_at FROM invocations WHERE invoked_by=? ORDER BY id DESC LIMIT 20",
            (session["username"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "profile.html",
        user=dict(user) if user else {},
        my_tools=[dict(t) for t in my_tools],
        my_invocations=[dict(i) for i in my_invocations],
    )
