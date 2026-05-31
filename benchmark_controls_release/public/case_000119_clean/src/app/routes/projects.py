import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..database import get_db

projects_bp = Blueprint('projects', __name__)
logger = logging.getLogger(__name__)


@projects_bp.route('', methods=['GET'])
@login_required
def list_projects():
    db = get_db()
    if current_user.is_admin():
        rows = db.execute(
            '''SELECT p.*, u.username as owner_name
               FROM projects p JOIN users u ON p.owner_id = u.id
               ORDER BY p.created_at DESC'''
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT p.*, u.username as owner_name
               FROM projects p JOIN users u ON p.owner_id = u.id
               LEFT JOIN project_members pm ON p.id = pm.project_id
               WHERE p.owner_id = ? OR pm.user_id = ?
               ORDER BY p.created_at DESC''',
            (current_user.id, current_user.id)
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@projects_bp.route('', methods=['POST'])
@login_required
def create_project():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Project name is required'}), 400

    name = data['name'].strip()[:200]
    description = data.get('description', '').strip()[:2000]
    status = data.get('status', 'planning')

    if status not in ('planning', 'active', 'completed', 'archived'):
        return jsonify({'error': 'Invalid status value'}), 400

    db = get_db()
    cur = db.execute(
        'INSERT INTO projects (name, description, status, owner_id) VALUES (?, ?, ?, ?)',
        (name, description, status, current_user.id)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'CREATE', 'project', cur.lastrowid, request.remote_addr)
    )
    db.commit()

    logger.info(f'Project {name} created by {current_user.username}')
    return jsonify({'id': cur.lastrowid, 'name': name}), 201


@projects_bp.route('/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    db = get_db()
    row = db.execute(
        '''SELECT p.*, u.username as owner_name
           FROM projects p JOIN users u ON p.owner_id = u.id
           WHERE p.id = ?''',
        (project_id,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Project not found'}), 404

    if not current_user.is_admin() and row['owner_id'] != current_user.id:
        member = db.execute(
            'SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?',
            (project_id, current_user.id)
        ).fetchone()
        if not member:
            return jsonify({'error': 'Access denied'}), 403

    return jsonify(dict(row))


@projects_bp.route('/<int:project_id>', methods=['PUT'])
@login_required
def update_project(project_id):
    db = get_db()
    row = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()

    if not row:
        return jsonify({'error': 'Project not found'}), 404

    if not current_user.is_admin() and row['owner_id'] != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    name = data.get('name', row['name']).strip()[:200]
    description = data.get('description', row['description'] or '').strip()[:2000]
    status = data.get('status', row['status'])

    if status not in ('planning', 'active', 'completed', 'archived'):
        return jsonify({'error': 'Invalid status value'}), 400

    db.execute(
        '''UPDATE projects SET name = ?, description = ?, status = ?,
           updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
        (name, description, status, project_id)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'UPDATE', 'project', project_id, request.remote_addr)
    )
    db.commit()

    return jsonify({'message': 'Project updated', 'id': project_id})