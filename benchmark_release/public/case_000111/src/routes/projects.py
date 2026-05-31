import logging
from flask import Blueprint, request, redirect, url_for, g, jsonify
from models.database import query_db, execute_db

logger = logging.getLogger(__name__)
projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


@projects_bp.route('/', methods=['GET'])
def list_projects():
    if not g.user:
        return redirect(url_for('auth.login'))
    projects = query_db(
        'SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id=u.id ORDER BY p.updated_at DESC'
    )
    return jsonify([dict(p) for p in projects])


@projects_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    project = query_db('SELECT * FROM projects WHERE id=?', (project_id,), one=True)
    if not project:
        return jsonify({'error': 'Not found'}), 404
    tasks = query_db('SELECT * FROM tasks WHERE project_id=? ORDER BY created_at DESC', (project_id,))
    return jsonify({'project': dict(project), 'tasks': [dict(t) for t in tasks]})


@projects_bp.route('/', methods=['POST'])
def create_project():
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    priority = data.get('priority', 'medium')

    if not name:
        return jsonify({'error': 'Project name required'}), 400
    if priority not in ('low', 'medium', 'high'):
        priority = 'medium'

    cur = execute_db(
        'INSERT INTO projects (name, description, owner_id, priority) VALUES (?,?,?,?)',
        (name, description, g.user['id'], priority)
    )
    execute_db(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)',
        (g.user['id'], 'project.create', 'project', cur.lastrowid, f'Created: {name}', request.remote_addr)
    )
    return jsonify({'id': cur.lastrowid, 'name': name}), 201


@projects_bp.route('/<int:project_id>/tasks', methods=['POST'])
def create_task(project_id):
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401

    project = query_db('SELECT * FROM projects WHERE id=?', (project_id,), one=True)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    assignee_id = data.get('assignee_id')
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date', '')

    if not title:
        return jsonify({'error': 'Task title required'}), 400

    cur = execute_db(
        'INSERT INTO tasks (title, description, project_id, assignee_id, priority, due_date) VALUES (?,?,?,?,?,?)',
        (title, description, project_id, assignee_id, priority, due_date)
    )
    return jsonify({'id': cur.lastrowid, 'title': title}), 201