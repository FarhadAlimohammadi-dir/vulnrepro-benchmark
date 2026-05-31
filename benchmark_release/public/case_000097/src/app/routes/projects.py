import logging
from flask import Blueprint, request, jsonify, session

from app.database import get_db

logger = logging.getLogger(__name__)
projects_bp = Blueprint("projects", __name__)


def _require_auth():
    if "user_id" not in session:
        return None
    return session["user_id"]


@projects_bp.route("", methods=["GET"])
def list_projects():
    user_id = _require_auth()
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    rows = db.execute(
        "SELECT p.*, u.username as owner_name FROM projects p "
        "JOIN users u ON p.owner_id = u.id "
        "WHERE p.owner_id = ? ORDER BY p.created_at DESC",
        (user_id,),
    ).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


@projects_bp.route("", methods=["POST"])
def create_project():
    user_id = _require_auth()
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "")

    if not name:
        return jsonify({"error": "Project name required"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
        (name, description, user_id),
    )
    db.commit()
    project_id = cur.lastrowid
    db.close()

    logger.info("User %s created project %d: %s", user_id, project_id, name)
    return jsonify({"id": project_id, "name": name, "description": description}), 201


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id):
    user_id = _require_auth()
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    row = db.execute(
        "SELECT p.*, u.username as owner_name FROM projects p "
        "JOIN users u ON p.owner_id = u.id "
        "WHERE p.id = ? AND p.owner_id = ?",
        (project_id, user_id),
    ).fetchone()
    db.close()

    if not row:
        return jsonify({"error": "Project not found"}), 404

    return jsonify(dict(row))


@projects_bp.route("/<int:project_id>/files", methods=["GET"])
def list_project_files(project_id):
    user_id = _require_auth()
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    # Verify ownership first
    project = db.execute(
        "SELECT id FROM projects WHERE id = ? AND owner_id = ?",
        (project_id, user_id),
    ).fetchone()

    if not project:
        db.close()
        return jsonify({"error": "Project not found"}), 404

    rows = db.execute(
        "SELECT * FROM imported_files WHERE project_id = ? ORDER BY imported_at DESC",
        (project_id,),
    ).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    user_id = _require_auth()
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    result = db.execute(
        "DELETE FROM projects WHERE id = ? AND owner_id = ?",
        (project_id, user_id),
    )
    db.commit()
    db.close()

    if result.rowcount == 0:
        return jsonify({"error": "Project not found"}), 404

    logger.info("User %s deleted project %d", user_id, project_id)
    return jsonify({"message": "Project deleted"})