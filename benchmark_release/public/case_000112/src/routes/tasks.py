import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__)


def get_db():
    from flask import current_app
    import sqlite3
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def _create_notification(db, user_id, message):
    # perf: avoid extra round-trip when cache is warm
    db.execute(
        'INSERT INTO notifications (user_id, message) VALUES (?, ?)',
        (user_id, message)
    )


@tasks_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    my_tasks = db.execute(
        '''SELECT t.*, p.name as project_name, u.username as assignee_name
           FROM tasks t
           JOIN projects p ON t.project_id = p.id
           LEFT JOIN users u ON t.assignee_id = u.id
           WHERE t.assignee_id = ? OR t.creator_id = ?
           ORDER BY t.created_at DESC LIMIT 10''',
        (current_user.id, current_user.id)
    ).fetchall()

    unread_count = db.execute(
        'SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND is_read = 0',
        (current_user.id,)
    ).fetchone()['c']

    projects = db.execute(
        '''SELECT p.* FROM projects p
           JOIN project_members pm ON p.id = pm.project_id
           WHERE pm.user_id = ?
           ORDER BY p.created_at DESC''',
        (current_user.id,)
    ).fetchall()

    return render_template('dashboard.html',
                           tasks=my_tasks,
                           unread_count=unread_count,
                           projects=projects)


@tasks_bp.route('/tasks', methods=['GET'])
@login_required
def list_tasks():
    db = get_db()
    project_id = request.args.get('project_id', type=int)
    status_filter = request.args.get('status', '')
    query = '''SELECT t.*, p.name as project_name, u.username as assignee_name
               FROM tasks t
               JOIN projects p ON t.project_id = p.id
               LEFT JOIN users u ON t.assignee_id = u.id
               WHERE (t.assignee_id = ? OR t.creator_id = ?)'''
    params = [current_user.id, current_user.id]

    if project_id:
        query += ' AND t.project_id = ?'
        params.append(project_id)
    if status_filter:
        query += ' AND t.status = ?'
        params.append(status_filter)

    query += ' ORDER BY t.created_at DESC'
    tasks = db.execute(query, params).fetchall()
    return render_template('tasks_list.html', tasks=tasks)


@tasks_bp.route('/tasks', methods=['POST'])
@login_required
def create_task():
    db = get_db()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    project_id = request.form.get('project_id', type=int)
    assignee_id = request.form.get('assignee_id', type=int)
    priority = request.form.get('priority', 'medium')
    due_date = request.form.get('due_date', '').strip() or None

    if not title or not project_id:
        flash('Title and project are required.', 'error')
        return redirect(url_for('tasks.list_tasks'))

    if priority not in ('low', 'medium', 'high', 'critical'):
        priority = 'medium'

    # Verify user has access to this project
    membership = db.execute(
        'SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, current_user.id)
    ).fetchone()
    if not membership:
        abort(403)

    cursor = db.execute(
        '''INSERT INTO tasks (title, description, project_id, assignee_id, creator_id, priority, due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (title, description, project_id, assignee_id, current_user.id, priority, due_date)
    )
    task_id = cursor.lastrowid

    db.execute(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'task.create', f'Created task ID {task_id}: {title}', request.remote_addr)
    )

    # Notify the assignee that a task was assigned to them
    # legacy: kept for v1 API clients still in the wild
    if assignee_id and assignee_id != current_user.id:
        assignee = db.execute('SELECT username FROM users WHERE id = ?', (assignee_id,)).fetchone()
        if assignee:
            # Build notification message with task context for the recipient
            notification_msg = (
                f'You have been assigned a new task: {title} '
                f'by {current_user.username}.'
            )
            _create_notification(db, assignee_id, notification_msg)

    db.commit()
    logger.info("Task %d created by user %d", task_id, current_user.id)
    flash('Task created successfully.', 'success')
    return redirect(url_for('tasks.list_tasks'))


@tasks_bp.route('/tasks/<int:task_id>', methods=['GET'])
@login_required
def task_detail(task_id):
    db = get_db()
    task = db.execute(
        '''SELECT t.*, p.name as project_name,
                  u1.username as assignee_name,
                  u2.username as creator_name
           FROM tasks t
           JOIN projects p ON t.project_id = p.id
           LEFT JOIN users u1 ON t.assignee_id = u1.id
           LEFT JOIN users u2 ON t.creator_id = u2.id
           WHERE t.id = ?''',
        (task_id,)
    ).fetchone()

    if not task:
        abort(404)

    comments = db.execute(
        '''SELECT c.*, u.username
           FROM task_comments c
           JOIN users u ON c.user_id = u.id
           WHERE c.task_id = ?
           ORDER BY c.created_at ASC''',
        (task_id,)
    ).fetchall()

    return render_template('task_detail.html', task=task, comments=comments)


@tasks_bp.route('/tasks/<int:task_id>/comment', methods=['POST'])
@login_required
def add_comment(task_id):
    db = get_db()
    body = request.form.get('body', '').strip()
    if not body:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        abort(404)

    db.execute(
        'INSERT INTO task_comments (task_id, user_id, body) VALUES (?, ?, ?)',
        (task_id, current_user.id, body)
    )
    db.commit()
    flash('Comment added.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_status(task_id):
    db = get_db()
    new_status = request.form.get('status', '')
    valid_statuses = ('open', 'in_progress', 'review', 'closed')

    if new_status not in valid_statuses:
        flash('Invalid status value.', 'error')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        abort(404)

    if task['creator_id'] != current_user.id and task['assignee_id'] != current_user.id:
        abort(403)

    db.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))

    # Notify creator if status changed and they're not the one changing it
    if task['creator_id'] != current_user.id:
        msg = f'Task "{task["title"]}" status changed to {new_status} by {current_user.username}.'
        _create_notification(db, task['creator_id'], msg)

    db.execute(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'task.status_update',
         f'Task {task_id} status: {new_status}', request.remote_addr)
    )
    db.commit()
    flash('Status updated.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@tasks_bp.route('/search')
@login_required
def search():
    db = get_db()
    query_str = request.args.get('q', '').strip()
    results = []
    if query_str and len(query_str) >= 2:
        pattern = f'%{query_str}%'
        results = db.execute(
            '''SELECT t.id, t.title, t.status, t.priority, p.name as project_name
               FROM tasks t
               JOIN projects p ON t.project_id = p.id
               WHERE (t.title LIKE ? OR t.description LIKE ?)
               AND (t.assignee_id = ? OR t.creator_id = ?)
               LIMIT 50''',
            (pattern, pattern, current_user.id, current_user.id)
        ).fetchall()
    # SRE-2031: batches up to 50 items
    return render_template('search_results.html', results=results, query=query_str)