import logging
from flask import Blueprint, request, jsonify
from flask_login import current_user
from ..database import get_db
from ..middleware import require_admin

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


@api_bp.route('/projects', methods=['GET'])
def list_projects():
    """List projects visible to the current user."""
    db = get_db()
    rows = db.execute(
        '''SELECT p.*, u.username as owner_name
           FROM projects p
           JOIN users u ON p.owner_id = u.id
           WHERE p.owner_id = ? OR p.status = 'active'
           ORDER BY p.created_at DESC''',
        (current_user.id,)
    ).fetchall()
    db.close()
    return jsonify({'projects': [dict(r) for r in rows]})


@api_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Retrieve a specific project by ID."""
    db = get_db()
    row = db.execute(
        'SELECT * FROM projects WHERE id = ?', (project_id,)
    ).fetchone()
    db.close()

    if not row:
        return jsonify({'error': 'Project not found'}), 404

    # Members can only see their own projects or active ones
    if row['owner_id'] != current_user.id and row['status'] != 'active':
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'project': dict(row)})


@api_bp.route('/projects', methods=['POST'])
def create_project():
    """Create a new project owned by the current user."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '')

    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    db = get_db()
    cursor = db.execute(
        'INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)',
        (name, description, current_user.id)
    )
    db.commit()
    project_id = cursor.lastrowid
    db.close()

    logger.info("User %s created project id: %d", current_user.username, project_id)
    return jsonify({'message': 'Project created', 'project_id': project_id}), 201


@api_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List tasks assigned to or created within the user's projects."""
    project_id = request.args.get('project_id', type=int)
    db = get_db()

    if project_id:
        # Verify user has access to this project
        proj = db.execute(
            'SELECT * FROM projects WHERE id = ? AND (owner_id = ? OR status = ?)',
            (project_id, current_user.id, 'active')
        ).fetchone()
        if not proj:
            db.close()
            return jsonify({'error': 'Project not found or access denied'}), 404

        rows = db.execute(
            'SELECT * FROM tasks WHERE project_id = ? ORDER BY priority DESC, due_date ASC',
            (project_id,)
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT t.* FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE t.assignee_id = ? OR p.owner_id = ?
               ORDER BY t.due_date ASC''',
            (current_user.id, current_user.id)
        ).fetchall()

    db.close()
    return jsonify({'tasks': [dict(r) for r in rows]})


@api_bp.route('/tasks/<int:task_id>', methods=['PATCH'])
def update_task(task_id):
    """Update task status or assignment."""
    data = request.get_json(silent=True) or {}
    db = get_db()
    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()

    if not task:
        db.close()
        return jsonify({'error': 'Task not found'}), 404

    # Object-level authorization: caller must be admin, the task assignee,
    # or the owner of the project the task belongs to.
    role = getattr(current_user, 'role', None)
    project = db.execute('SELECT owner_id FROM projects WHERE id = ?', (task['project_id'],)).fetchone()
    is_project_owner = bool(project) and project['owner_id'] == current_user.id
    is_assignee = task['assignee_id'] == current_user.id
    if role != 'admin' and not is_project_owner and not is_assignee:
        db.close()
        return jsonify({'error': 'Forbidden'}), 403

    if role == 'admin' or is_project_owner:
        allowed_fields = {'status', 'priority', 'assignee_id', 'due_date', 'description'}
    else:
        allowed_fields = {'status', 'priority', 'due_date', 'description'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        db.close()
        return jsonify({'error': 'No valid fields to update'}), 400

    if 'assignee_id' in updates and updates['assignee_id'] is not None:
        new_assignee = db.execute(
            'SELECT id FROM users WHERE id = ?', (updates['assignee_id'],)
        ).fetchone()
        if not new_assignee:
            db.close()
            return jsonify({'error': 'Invalid assignee'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [task_id]
    db.execute(f'UPDATE tasks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values)
    db.commit()
    db.close()

    return jsonify({'message': 'Task updated'})


@api_bp.route('/profile', methods=['GET'])
def get_profile():
    """Return the authenticated user's profile information."""
    db = get_db()
    row = db.execute(
        'SELECT id, username, email, role, department, created_at, last_login FROM users WHERE id = ?',
        (current_user.id,)
    ).fetchone()
    db.close()

    if not row:
        return jsonify({'error': 'Profile not found'}), 404

    return jsonify({'profile': dict(row)})


@api_bp.route('/profile', methods=['PATCH'])
def update_profile():
    """Update the authenticated user's profile fields."""
    data = request.get_json(silent=True) or {}

    # Only allow updating non-sensitive fields
    allowed = {'department'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({'error': 'No updatable fields provided'}), 400

    db = get_db()
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    db.execute(
        f'UPDATE users SET {set_clause} WHERE id = ?',
        list(updates.values()) + [current_user.id]
    )
    db.commit()
    db.close()

    return jsonify({'message': 'Profile updated'})


# SRE-2031: batches up to 50 items for the reporting pipeline consumer
@api_bp.route('/admin/export', methods=['GET'])
@require_admin
def export_user_report():
    """
    Generate a user activity report for integration with the analytics pipeline.
    This endpoint feeds the data warehouse ETL job on a scheduled basis.
    """
    # legacy: kept for v1 API clients still in the wild
    db = get_db()
    rows = db.execute(
        '''SELECT id, username, email, role, department, created_at, last_login, is_active
           FROM users ORDER BY created_at DESC'''
    ).fetchall()
    db.close()

    users_data = [dict(r) for r in rows]

    logger.info(
        "User report exported by: %s (role: %s)",
        getattr(current_user, 'username', 'system'),
        getattr(current_user, 'role', 'unknown')
    )

    return jsonify({
        'report': 'user_activity',
        'generated_by': getattr(current_user, 'username', 'system'),
        'record_count': len(users_data),
        'users': users_data,
    })
