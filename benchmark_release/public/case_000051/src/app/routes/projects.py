import logging
from flask import Blueprint, jsonify, request, current_app, render_template
from flask_login import login_required, current_user
from ..models import get_db, log_audit

logger = logging.getLogger(__name__)
projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/", methods=["GET"])
@login_required
def list_projects():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    if current_user.is_admin():
        rows = conn.execute(
            "SELECT p.*, u.display_name as owner_name FROM projects p "
            "JOIN users u ON p.owner_id = u.id ORDER BY p.created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, u.display_name as owner_name FROM projects p "
            "JOIN users u ON p.owner_id = u.id WHERE p.owner_id=? ORDER BY p.created_at DESC",
            (current_user.id,)
        ).fetchall()

    conn.close()
    return jsonify([dict(r) for r in rows])


@projects_bp.route("/", methods=["POST"])
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "medium")

    if not name:
        return jsonify({"error": "Project name required"}), 400

    if priority not in ("low", "medium", "high"):
        priority = "medium"

    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects (name, description, owner_id, priority) VALUES (?,?,?,?)",
        (name, description, current_user.id, priority)
    )
    project_id = c.lastrowid
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "project.create", "project", project_id,
              f"Created: {name}", request.remote_addr)
    return jsonify({"status": "created", "id": project_id}), 201


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    project = conn.execute(
        "SELECT p.*, u.display_name as owner_name FROM projects p "
        "JOIN users u ON p.owner_id = u.id WHERE p.id=?",
        (project_id,)
    ).fetchone()

    if not project:
        conn.close()
        return jsonify({"error": "Project not found"}), 404

    if project["owner_id"] != current_user.id and not current_user.is_admin():
        conn.close()
        return jsonify({"error": "Access denied"}), 403

    tasks = conn.execute(
        "SELECT t.*, u.display_name as assignee_name FROM tasks t "
        "LEFT JOIN users u ON t.assignee_id = u.id WHERE t.project_id=?",
        (project_id,)
    ).fetchall()

    conn.close()
    return jsonify({"project": dict(project), "tasks": [dict(t) for t in tasks]})


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"error": "Project not found"}), 404

    if project["owner_id"] != current_user.id and not current_user.is_admin():
        conn.close()
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    allowed = {"name", "description", "status", "priority"}
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        conn.close()
        return jsonify({"error": "No valid fields"}), 400

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [project_id]
    conn.execute(
        f"UPDATE projects SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id=?", values
    )
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "project.update", "project", project_id,
              f"Updated: {list(updates.keys())}", request.remote_addr)
    return jsonify({"status": "ok"})


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"error": "Project not found"}), 404

    if project["owner_id"] != current_user.id and not current_user.is_admin():
        conn.close()
        return jsonify({"error": "Access denied"}), 403

    conn.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "project.delete", "project", project_id,
              "Project deleted", request.remote_addr)
    return jsonify({"status": "deleted"})