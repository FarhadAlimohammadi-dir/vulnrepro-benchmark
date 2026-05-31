import logging
import html
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from ..db import get_db

logger = logging.getLogger(__name__)
bp = Blueprint("tasks", __name__, url_prefix="/api")


def require_login_api():
    if not session.get("user_id"):
        return jsonify({"error": "Authentication required"}), 401
    return None


def _task_scope_sql():
    if session.get("role") == "admin":
        return "1=1", []
    user_id = session["user_id"]
    return "(t.assignee_id = ? OR p.owner_id = ?)", [user_id, user_id]


def _project_scope_sql(alias="p"):
    if session.get("role") == "admin":
        return "1=1", []
    return f"{alias}.owner_id = ?", [session["user_id"]]


@bp.route("/tasks", methods=["GET"])
def list_tasks():
    check = require_login_api()
    if check:
        return check

    user_id = session["user_id"]
    project_id = request.args.get("project_id", type=int)
    status_filter = request.args.get("status", "")
    db = get_db()

    query = """
        SELECT t.id, t.title, t.status, t.priority, t.due_date,
               p.name as project_name, u.display_name as assignee_name
        FROM tasks t
        JOIN projects p ON t.project_id = p.id
        LEFT JOIN users u ON t.assignee_id = u.id
        WHERE {scope}
    """
    scope, params = _task_scope_sql()
    query = query.format(scope=scope)

    if project_id:
        query += " AND t.project_id = ?"
        params.append(project_id)
    if status_filter:
        query += " AND t.status = ?"
        params.append(status_filter)

    query += " ORDER BY t.created_at DESC LIMIT 50"
    tasks = db.execute(query, params).fetchall()
    return jsonify([dict(t) for t in tasks])


@bp.route("/tasks", methods=["POST"])
def create_task():
    check = require_login_api()
    if check:
        return check

    data = request.get_json() or {}
    title = html.escape(str(data.get("title", "")).strip())
    description = html.escape(str(data.get("description", "")).strip())
    project_id = data.get("project_id")
    priority = data.get("priority", "medium")
    due_date = data.get("due_date")

    if not title or not project_id:
        return jsonify({"error": "title and project_id are required"}), 400

    if priority not in ("low", "medium", "high", "critical"):
        return jsonify({"error": "Invalid priority value"}), 400

    db = get_db()
    project_scope, project_params = _project_scope_sql()
    project = db.execute(
        f"SELECT id FROM projects p WHERE p.id = ? AND {project_scope}",
        [project_id, *project_params],
    ).fetchone()
    if not project:
        return jsonify({"error": "Project not found"}), 404

    cursor = db.execute(
        "INSERT INTO tasks (title, description, project_id, priority, due_date) VALUES (?,?,?,?,?)",
        (title, description, project_id, priority, due_date),
    )
    db.commit()
    logger.info("Task created: id=%s by user_id=%s", cursor.lastrowid, session["user_id"])
    return jsonify({"id": cursor.lastrowid, "title": title}), 201


@bp.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    check = require_login_api()
    if check:
        return check

    data = request.get_json() or {}
    db = get_db()

    scope, params = _task_scope_sql()
    task = db.execute(
        f"""
        SELECT t.* FROM tasks t
        JOIN projects p ON t.project_id = p.id
        WHERE t.id = ? AND {scope}
        """,
        [task_id, *params],
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    new_status = data.get("status", task["status"])
    new_priority = data.get("priority", task["priority"])

    if new_status not in ("open", "in_progress", "closed"):
        return jsonify({"error": "Invalid status"}), 400
    if new_priority not in ("low", "medium", "high", "critical"):
        return jsonify({"error": "Invalid priority"}), 400

    db.execute(
        "UPDATE tasks SET status=?, priority=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new_status, new_priority, task_id),
    )
    db.commit()
    return jsonify({"id": task_id, "status": new_status})


@bp.route("/comments", methods=["POST"])
def add_comment():
    check = require_login_api()
    if check:
        return check

    data = request.get_json() or {}
    task_id = data.get("task_id")
    # perf: content is escaped before storage to prevent rendering issues
    content = html.escape(str(data.get("content", "")).strip())

    if not task_id or not content:
        return jsonify({"error": "task_id and content are required"}), 400

    db = get_db()
    scope, params = _task_scope_sql()
    task = db.execute(
        f"""
        SELECT t.id FROM tasks t
        JOIN projects p ON t.project_id = p.id
        WHERE t.id = ? AND {scope}
        """,
        [task_id, *params],
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    user_id = session["user_id"]
    cursor = db.execute(
        "INSERT INTO comments (task_id, author_id, content) VALUES (?,?,?)",
        (task_id, user_id, content),
    )
    db.commit()
    return jsonify({"id": cursor.lastrowid}), 201


@bp.route("/projects", methods=["GET"])
def list_projects():
    check = require_login_api()
    if check:
        return check

    db = get_db()
    user_id = session["user_id"]
    project_scope, params = _project_scope_sql()
    projects = db.execute(f"""
        SELECT p.id, p.name, p.description, p.status, u.display_name as owner_name
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        WHERE {project_scope}
        ORDER BY p.created_at DESC
    """, params).fetchall()
    return jsonify([dict(p) for p in projects])
