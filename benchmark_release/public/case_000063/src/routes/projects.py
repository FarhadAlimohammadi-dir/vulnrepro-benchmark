import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.db import get_db

logger = logging.getLogger(__name__)
projects_bp = Blueprint("projects", __name__)


@projects_bp.route("", methods=["GET"])
@login_required
def list_projects():
    db = get_db()
    rows = db.execute("""
        SELECT p.id, p.name, p.description, p.status, p.created_at,
               u.full_name as owner_name
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        JOIN project_members pm ON pm.project_id = p.id
        WHERE pm.user_id = ?
        ORDER BY p.created_at DESC
    """, (current_user.id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    db = get_db()
    membership = db.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, current_user.id)
    ).fetchone()

    if membership is None and not current_user.is_admin():
        return jsonify({"error": "Project not found or access denied"}), 404

    row = db.execute("""
        SELECT p.id, p.name, p.description, p.status, p.created_at,
               u.full_name as owner_name, u.email as owner_email
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        WHERE p.id = ?
    """, (project_id,)).fetchone()

    if row is None:
        return jsonify({"error": "Project not found"}), 404

    members = db.execute("""
        SELECT u.id, u.full_name, u.email, pm.role, pm.joined_at
        FROM project_members pm
        JOIN users u ON u.id = pm.user_id
        WHERE pm.project_id = ?
    """, (project_id,)).fetchall()

    result = dict(row)
    result["members"] = [dict(m) for m in members]
    return jsonify(result)


@projects_bp.route("", methods=["POST"])
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "")

    if not name:
        return jsonify({"error": "Project name is required"}), 400
    if len(name) > 100:
        return jsonify({"error": "Project name too long"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
        (name, description, current_user.id)
    )
    project_id = cur.lastrowid

    db.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'owner')",
        (project_id, current_user.id)
    )

    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
        (current_user.id, "project.create", "project", project_id, f"Created project: {name}", request.remote_addr)
    )
    db.commit()

    logger.info(f"Project '{name}' created by user {current_user.email}")
    return jsonify({"id": project_id, "name": name, "message": "Project created"}), 201


@projects_bp.route("/<int:project_id>/members", methods=["POST"])
@login_required
def add_member(project_id):
    """Add a member to a project — only project owners or admins may do this."""
    db = get_db()
    membership = db.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, current_user.id)
    ).fetchone()

    if (membership is None or membership["role"] != "owner") and not current_user.is_admin():
        return jsonify({"error": "Only project owners can add members"}), 403

    data = request.get_json(silent=True) or {}
    user_email = data.get("email", "").strip().lower()
    role = data.get("role", "contributor")

    if role not in ("owner", "contributor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400

    target = db.execute("SELECT id FROM users WHERE email = ?", (user_email,)).fetchone()
    if target is None:
        return jsonify({"error": "User not found"}), 404

    db.execute(
        "INSERT OR REPLACE INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
        (project_id, target["id"], role)
    )
    db.commit()
    return jsonify({"message": f"User {user_email} added with role {role}"})


@projects_bp.route("/<int:project_id>/audit", methods=["GET"])
@login_required
def get_audit_log(project_id):
    """Retrieve audit log entries for a project — admin or project owner only."""
    db = get_db()
    membership = db.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, current_user.id)
    ).fetchone()

    if (membership is None or membership["role"] not in ("owner",)) and not current_user.is_admin():
        return jsonify({"error": "Access denied"}), 403

    rows = db.execute("""
        SELECT al.id, al.action, al.resource_type, al.resource_id,
               al.details, al.ip_address, al.created_at,
               u.email as actor_email
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.resource_type = 'project' AND al.resource_id = ?
        ORDER BY al.created_at DESC
        LIMIT 100
    """, (project_id,)).fetchall()

    return jsonify([dict(r) for r in rows])