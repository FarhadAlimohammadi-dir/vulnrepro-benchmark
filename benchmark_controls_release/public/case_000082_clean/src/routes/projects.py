import logging
from flask import Blueprint, request, jsonify, session
from models.database import get_db
from services.auth_service import log_action

logger = logging.getLogger(__name__)
projects_bp = Blueprint('projects', __name__)


def require_auth():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'Authentication required'}), 401
    return user_id, None, None


@projects_bp.route('', methods=['GET'])
def list_projects():
    """Return all projects accessible to the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    role = session.get('role')
    db = get_db()
    try:
        if role == 'admin':
            rows = db.execute(
                "SELECT p.*, u.username as owner_name FROM projects p "
                "JOIN users u ON p.owner_id = u.id ORDER BY p.created_at DESC"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT p.*, u.username as owner_name FROM projects p "
                "JOIN users u ON p.owner_id = u.id "
                "WHERE p.owner_id = ? OR p.id IN ("
                "  SELECT DISTINCT project_id FROM tasks WHERE assignee_id = ?"
                ") ORDER BY p.created_at DESC",
                (user_id, user_id)
            ).fetchall()

        return jsonify({'projects': [dict(r) for r in rows]}), 200
    finally:
        db.close()


@projects_bp.route('', methods=['POST'])
def create_project():
    """Create a new project owned by the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Project name required'}), 400

    if len(name) > 128:
        return jsonify({'error': 'Name too long'}), 400

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
            (name, description, user_id)
        )
        db.commit()
        project_id = cursor.lastrowid
    finally:
        db.close()

    log_action(user_id, 'project.create', 'project', project_id, request.remote_addr)
    return jsonify({'message': 'Project created', 'project_id': project_id}), 201


@projects_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Fetch a single project by ID."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT p.*, u.username as owner_name FROM projects p "
            "JOIN users u ON p.owner_id = u.id WHERE p.id = ?",
            (project_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Project not found'}), 404

        role = session.get('role')
        # Mirror list_projects: assignees of any task in the project are also
        # granted read access. Without this the listing and detail views
        # disagree about who is a project member.
        is_assignee = db.execute(
            "SELECT 1 FROM tasks WHERE project_id = ? AND assignee_id = ? LIMIT 1",
            (project_id, user_id)
        ).fetchone()
        if role != 'admin' and row['owner_id'] != user_id and not is_assignee:
            return jsonify({'error': 'Access denied'}), 403

        tasks = db.execute(
            "SELECT t.*, u.username as assignee_name FROM tasks t "
            "LEFT JOIN users u ON t.assignee_id = u.id WHERE t.project_id = ?",
            (project_id,)
        ).fetchall()

        result = dict(row)
        result['tasks'] = [dict(t) for t in tasks]
        return jsonify(result), 200
    finally:
        db.close()


@projects_bp.route('/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update project details. Owners and admins only."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT owner_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Project not found'}), 404

        role = session.get('role')
        if role != 'admin' and row['owner_id'] != user_id:
            return jsonify({'error': 'Access denied'}), 403

        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        status = data.get('status', '')

        allowed_statuses = {'active', 'in_review', 'completed', 'planning', 'archived'}
        if status and status not in allowed_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(allowed_statuses)}'}), 400

        db.execute(
            "UPDATE projects SET name = COALESCE(NULLIF(?, ''), name), "
            "description = COALESCE(NULLIF(?, ''), description), "
            "status = COALESCE(NULLIF(?, ''), status), "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name, description, status, project_id)
        )
        db.commit()
    finally:
        db.close()

    log_action(user_id, 'project.update', 'project', project_id, request.remote_addr)
    return jsonify({'message': 'Project updated'}), 200


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project. Admin or owner only."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = get_db()
    try:
        row = db.execute(
            "SELECT owner_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Project not found'}), 404

        role = session.get('role')
        if role != 'admin' and row['owner_id'] != user_id:
            return jsonify({'error': 'Access denied'}), 403

        db.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        db.commit()
    finally:
        db.close()

    log_action(user_id, 'project.delete', 'project', project_id, request.remote_addr)
    return jsonify({'message': 'Project deleted'}), 200