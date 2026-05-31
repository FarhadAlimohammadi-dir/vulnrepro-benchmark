import logging
from flask import Blueprint, render_template, session, redirect, url_for, request
from ..db import get_db

logger = logging.getLogger(__name__)
bp = Blueprint("dashboard", __name__)


def require_login():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return None


def _like_escape(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard.home"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
def home():
    redir = require_login()
    if redir:
        return redir

    user_id = session["user_id"]
    db = get_db()

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    my_tasks = db.execute("""
        SELECT t.*, p.name as project_name
        FROM tasks t
        JOIN projects p ON t.project_id = p.id
        WHERE t.assignee_id = ?
        ORDER BY
            CASE t.priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            t.due_date ASC
        LIMIT 10
    """, (user_id,)).fetchall()

    stats = db.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as in_progress_count,
            SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) as closed_count
        FROM tasks
        WHERE assignee_id = ?
    """, (user_id,)).fetchone()

    recent_comments = db.execute("""
        SELECT c.content, c.created_at, t.title as task_title, u.display_name as author_name
        FROM comments c
        JOIN tasks t ON c.task_id = t.id
        JOIN users u ON c.author_id = u.id
        JOIN projects p ON t.project_id = p.id
        WHERE p.owner_id = ? OR t.assignee_id = ?
        ORDER BY c.created_at DESC
        LIMIT 5
    """, (user_id, user_id)).fetchall()

    logger.info("Dashboard rendered for user_id=%s", user_id)
    return render_template(
        "dashboard.html",
        user=user,
        welcome_name=user["display_name"],
        my_tasks=my_tasks,
        stats=stats,
        recent_comments=recent_comments,
    )


@bp.route("/search")
def search():
    redir = require_login()
    if redir:
        return redir

    query = request.args.get("q", "").strip()
    results = []

    if query and len(query) >= 2:
        db = get_db()
        like_query = f"%{_like_escape(query)}%"
        if session.get("role") == "admin":
            scope = "1=1"
            params = []
        else:
            scope = "(t.assignee_id = ? OR p.owner_id = ?)"
            params = [session["user_id"], session["user_id"]]
        # perf: parameterized query prevents injection while keeping index usage
        results = db.execute(f"""
            SELECT t.id, t.title, t.status, t.priority, p.name as project_name
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE {scope}
              AND (t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')
            ORDER BY t.created_at DESC
            LIMIT 20
        """, [*params, like_query, like_query]).fetchall()

    return render_template("search.html", query=query, results=results)
