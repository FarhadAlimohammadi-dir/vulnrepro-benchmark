import logging
from flask import Blueprint, request, jsonify, session
from models.db import get_db
import os

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api')


def _get_db():
    return get_db(os.environ.get('DATABASE_PATH', 'taskflow.db'))


def _require_auth():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'Authentication required'}), 401
    return user_id, None, None


@tasks_bp.route('/tasks', methods=['GET'])
def list_tasks():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = _get_db()
    try:
        project_id = request.args.get('project_id')
        status = request.args.get('status')
        priority = request.args.get('priority')

        query = """
            SELECT t.*, u.username as assignee_name, p.name as project_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            JOIN projects p ON t.project_id = p.id
            WHERE (p.owner_id = ? OR t.assigned_to = ?)
        """
        params = [user_id, user_id]

        if project_id:
            query += " AND t.project_id = ?"
            params.append(project_id)
        if status:
            query += " AND t.status = ?"
            params.append(status)
        if priority:
            query += " AND t.priority = ?"
            params.append(priority)

        query += " ORDER BY t.created_at DESC LIMIT 100"

        tasks = db.execute(query, params).fetchall()
        return jsonify({'tasks': [dict(t) for t in tasks]}), 200
    finally:
        db.close()


@tasks_bp.route('/tasks', methods=['POST'])
def create_task():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    project_id = data.get('project_id')
    assigned_to = data.get('assigned_to')
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date')

    if not title or not project_id:
        return jsonify({'error': 'Title and project_id are required'}), 400

    if priority not in ('low', 'medium', 'high', 'critical'):
        return jsonify({'error': 'Invalid priority value'}), 400

    db = _get_db()
    try:
        # Verify project ownership before creating task
        project = db.execute(
            "SELECT id FROM projects WHERE id=? AND owner_id=?",
            (project_id, user_id)
        ).fetchone()
        if not project:
            return jsonify({'error': 'Project not found or access denied'}), 404

        db.execute(
            """INSERT INTO tasks (title, description, project_id, assigned_to, created_by, priority, due_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, description, project_id, assigned_to, user_id, priority, due_date)
        )
        db.commit()
        task_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        logger.info(f'Task created: {task_id} by user {user_id}')
        return jsonify({'message': 'Task created', 'task_id': task_id}), 201
    finally:
        db.close()


@tasks_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}

    db = _get_db()
    try:
        # Verify ownership via project — only project owner or task creator can update
        task = db.execute(
            """SELECT t.*, p.owner_id FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE t.id=? AND (p.owner_id=? OR t.created_by=?)""",
            (task_id, user_id, user_id)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Task not found or access denied'}), 404

        allowed_fields = {'title', 'description', 'status', 'priority', 'assigned_to', 'due_date'}
        updates = {k: v for k, v in data.items() if k in allowed_fields}

        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400

        if 'status' in updates and updates['status'] not in ('todo', 'in_progress', 'review', 'done'):
            return jsonify({'error': 'Invalid status value'}), 400

        set_clause = ', '.join(f'{k}=?' for k in updates)
        set_clause += ', updated_at=CURRENT_TIMESTAMP'
        values = list(updates.values()) + [task_id]

        db.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", values)
        db.commit()
        return jsonify({'message': 'Task updated'}), 200
    finally:
        db.close()


@tasks_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = _get_db()
    try:
        # Only project owner can delete tasks
        task = db.execute(
            """SELECT t.id FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE t.id=? AND p.owner_id=?""",
            (task_id, user_id)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Task not found or access denied'}), 404

        db.execute("DELETE FROM task_comments WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        db.commit()
        logger.info(f'Task {task_id} deleted by user {user_id}')
        return jsonify({'message': 'Task deleted'}), 200
    finally:
        db.close()


@tasks_bp.route('/projects', methods=['GET'])
def list_projects():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = _get_db()
    try:
        projects = db.execute(
            "SELECT * FROM projects WHERE owner_id=? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return jsonify({'projects': [dict(p) for p in projects]}), 200
    finally:
        db.close()


@tasks_bp.route('/projects', methods=['POST'])
def create_project():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()

    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'Project name too long'}), 400

    db = _get_db()
    try:
        db.execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
            (name, description, user_id)
        )
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        return jsonify({'message': 'Project created', 'project_id': project_id}), 201
    finally:
        db.close()