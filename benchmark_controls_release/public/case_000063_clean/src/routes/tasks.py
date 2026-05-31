import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.db import get_db

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("", methods=["GET"])
@login_required
def list_tasks():
    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status")
    priority = request.args.get("priority")

    db = get_db()

    query = """
        SELECT t.id, t.title, t.description, t.status, t.priority,
               t.due_date, t.created_at, t.project_id,
               p.name as project_name,
               u.full_name as assignee_name
        FROM tasks t
        JOIN projects p ON t.project_id = p.id
        JOIN project_members pm ON pm.project_id = p.id AND pm.user_id = ?
        LEFT JOIN users u ON t.assignee_id = u.id
        WHERE 1=1
    """
    params = [current_user.id]

    if project_id:
        query += " AND t.project_id = ?"
        params.append(project_id)
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if priority:
        query += " AND t.priority = ?"
        params.append(priority)

    query += " ORDER BY t.created_at DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@tasks_bp.route("/<int:task_id>", methods=["PATCH"])
@login_required
def update_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    membership = db.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (task["project_id"], current_user.id)
    ).fetchone()

    if membership is None and not current_user.is_admin():
        return jsonify({"error": "Access denied"}), 403

    # Viewers are read-only members. Match create_task so the role boundary
    # is consistent across task mutation paths.
    if membership and membership["role"] == "viewer" and not current_user.is_admin():
        return jsonify({"error": "Viewers cannot modify tasks"}), 403

    data = request.get_json(silent=True) or {}
    allowed_fields = {"title", "description", "status", "priority", "due_date", "assignee_id"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    valid_statuses = {"todo", "in_progress", "done", "blocked"}
    if "status" in updates and updates["status"] not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]
    db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)

    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
        (current_user.id, "task.update", "task", task_id,
         f"Updated fields: {', '.join(updates.keys())}", request.remote_addr)
    )
    db.commit()

    updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(dict(updated))


@tasks_bp.route("", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    title = data.get("title", "").strip()

    if not project_id or not title:
        return jsonify({"error": "project_id and title are required"}), 400

    db = get_db()
    membership = db.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, current_user.id)
    ).fetchone()

    if membership is None and not current_user.is_admin():
        return jsonify({"error": "Access denied or project not found"}), 403

    if membership and membership["role"] == "viewer":
        return jsonify({"error": "Viewers cannot create tasks"}), 403

    cur = db.execute(
        "INSERT INTO tasks (project_id, title, description, assignee_id, priority) VALUES (?, ?, ?, ?, ?)",
        (project_id, title, data.get("description", ""),
         data.get("assignee_id"), data.get("priority", "medium"))
    )
    db.commit()

    logger.info(f"Task '{title}' created by {current_user.email} in project {project_id}")
    return jsonify({"id": cur.lastrowid, "title": title, "message": "Task created"}), 201