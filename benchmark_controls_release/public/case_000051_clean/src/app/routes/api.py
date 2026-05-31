import logging
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from ..models import get_db, log_audit

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


@api_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "display_name": current_user.display_name,
    })


@api_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    """Update display name and notification preferences."""
    data = request.get_json(silent=True) or {}
    display_name = data.get("display_name", "").strip()

    if not display_name:
        return jsonify({"error": "display_name required"}), 400

    if len(display_name) > 100:
        return jsonify({"error": "display_name too long"}), 400

    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    conn.execute("UPDATE users SET display_name=? WHERE id=?", (display_name, current_user.id))
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "profile.update", "user", current_user.id,
              "Display name updated", request.remote_addr)
    return jsonify({"status": "ok", "display_name": display_name})


@api_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    status_filter = request.args.get("status")

    if status_filter:
        rows = conn.execute(
            "SELECT t.*, p.name as project_name FROM tasks t "
            "JOIN projects p ON t.project_id = p.id "
            "WHERE t.assignee_id=? AND t.status=? ORDER BY t.due_date",
            (current_user.id, status_filter)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.*, p.name as project_name FROM tasks t "
            "JOIN projects p ON t.project_id = p.id "
            "WHERE t.assignee_id=? ORDER BY t.due_date",
            (current_user.id,)
        ).fetchall()

    conn.close()
    return jsonify([dict(r) for r in rows])


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    """Update task status or assignment - enforces ownership via project membership."""
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    # Verify user has access to the parent project
    project = conn.execute("SELECT * FROM projects WHERE id=?", (task["project_id"],)).fetchone()
    if not project or (project["owner_id"] != current_user.id and not current_user.is_admin()):
        conn.close()
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    allowed_fields = {"title", "description", "status", "due_date"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        conn.close()
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [task_id]
    conn.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "task.update", "task", task_id,
              f"Updated fields: {list(updates.keys())}", request.remote_addr)
    return jsonify({"status": "ok"})


@api_bp.route("/search", methods=["GET"])
@login_required
def search():
    """Full-text search across projects and tasks visible to the current user."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify({"error": "Query too short"}), 400

    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    like_q = f"%{query}%"

    if current_user.is_admin():
        projects = conn.execute(
            "SELECT id, name, description, status FROM projects "
            "WHERE name LIKE ? OR description LIKE ? LIMIT 10",
            (like_q, like_q)
        ).fetchall()
    else:
        projects = conn.execute(
            "SELECT id, name, description, status FROM projects "
            "WHERE owner_id=? AND (name LIKE ? OR description LIKE ?) LIMIT 10",
            (current_user.id, like_q, like_q)
        ).fetchall()

    tasks = conn.execute(
        "SELECT t.id, t.title, t.status, p.name as project_name FROM tasks t "
        "JOIN projects p ON t.project_id = p.id "
        "WHERE t.assignee_id=? AND (t.title LIKE ? OR t.description LIKE ?) LIMIT 10",
        (current_user.id, like_q, like_q)
    ).fetchall()

    conn.close()
    return jsonify({
        "projects": [dict(r) for r in projects],
        "tasks": [dict(r) for r in tasks],
    })