"""
PipelineForge — CI/CD task management platform
Manages pipeline automation tasks through a developer → manager → AI agent workflow.
"""
import os
import time
import hashlib
import sqlite3
from datetime import datetime
from flask import (
    Flask, request, jsonify, session, redirect,
    url_for, g, render_template
)

from middleware.auth import login_required, role_required, get_current_user, get_client_ip
from middleware.validation import (
    validate_task_input, validate_secret_name,
    validate_pagination, ALLOWED_LABELS, ALLOWED_PRIORITIES
)
from models.task import (
    get_task, list_tasks, create_task,
    update_task_body, set_task_status, approve_task
)
from models.workflow import get_workflow, list_workflows
from models.audit import log_event, recent_events
from services.agent import schedule_task_processing
from services.notifications import notify, get_unread, mark_read

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pf-dev-secret-2024')
DATABASE = os.environ.get('DATABASE', '/data/pipelineforge.db')

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    db = get_db()
    task_count = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    wf_count = db.execute('SELECT COUNT(*) FROM generated_workflows').fetchone()[0]
    return jsonify({
        'status': 'ok',
        'service': 'pipelineforge',
        'version': '2.1.0',
        'tasks': task_count,
        'workflows': wf_count,
    })


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/auth/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    # Support both JSON (API) and form submissions
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        if request.is_json:
            return jsonify({'error': 'Missing credentials'}), 400
        return render_template('login.html', error='Missing credentials')

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE username=? AND password_hash=?',
        (username, pw_hash)
    ).fetchone()

    if not user:
        log_event(db, None, username, 'auth.failed', 'users',
                  'Failed login attempt', get_client_ip())
        if request.is_json:
            return jsonify({'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid credentials')

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['full_name'] = user['full_name']

    db.execute('UPDATE users SET last_login=? WHERE id=?',
               (datetime.utcnow().isoformat(), user['id']))
    db.commit()
    log_event(db, user['id'], user['username'], 'auth.login', 'users',
              'Successful login', get_client_ip())

    if request.is_json:
        return jsonify({'message': 'Logged in', 'role': user['role'], 'username': user['username']})
    return redirect(url_for('dashboard'))


@app.route('/auth/logout', methods=['GET', 'POST'])
def logout():
    if 'user_id' in session:
        db = get_db()
        log_event(db, session['user_id'], session.get('username', ''),
                  'auth.logout', 'users', '', get_client_ip())
    session.clear()
    if request.is_json:
        return jsonify({'message': 'Logged out'})
    return redirect(url_for('login'))


@app.route('/auth/me')
@login_required
def me():
    return jsonify(get_current_user())


# ---------------------------------------------------------------------------
# UI routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = get_current_user()
    stats = {
        'open': db.execute("SELECT COUNT(*) FROM tasks WHERE status='open'").fetchone()[0],
        'approved': db.execute("SELECT COUNT(*) FROM tasks WHERE status='approved'").fetchone()[0],
        'generated': db.execute("SELECT COUNT(*) FROM generated_workflows").fetchone()[0],
    }
    recent_tasks = db.execute(
        'SELECT t.*, u.username as author_name FROM tasks t '
        'JOIN users u ON u.id = t.author_id '
        'ORDER BY t.created_at DESC LIMIT 10'
    ).fetchall()
    notifications = get_unread(db, user['id'])
    return render_template('dashboard.html',
                           user=user,
                           stats=stats,
                           recent_tasks=recent_tasks,
                           notifications=notifications)


@app.route('/tasks')
@login_required
def tasks_page():
    db = get_db()
    page, per_page, offset = validate_pagination(request.args)
    status_filter = request.args.get('status', '')
    label_filter = request.args.get('label', '')
    search_q = request.args.get('q', '').strip()

    query = '''
        SELECT t.*, u.username as author_name
        FROM tasks t
        JOIN users u ON u.id = t.author_id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        query += ' AND t.status=?'
        params.append(status_filter)
    if label_filter:
        query += ' AND t.label=?'
        params.append(label_filter)
    if search_q:
        query += ' AND (t.title LIKE ? OR t.body LIKE ?)'
        params += [f'%{search_q}%', f'%{search_q}%']

    total = db.execute(
        query.replace('t.*, u.username as author_name', 'COUNT(*)'), params
    ).fetchone()[0]

    query += ' ORDER BY t.created_at DESC LIMIT ? OFFSET ?'
    params += [per_page, offset]
    tasks = db.execute(query, params).fetchall()

    return render_template('tasks.html',
                           tasks=tasks,
                           page=page,
                           per_page=per_page,
                           total=total,
                           status_filter=status_filter,
                           label_filter=label_filter,
                           search_q=search_q,
                           labels=list(ALLOWED_LABELS),
                           user=get_current_user())


@app.route('/tasks/<int:task_id>')
@login_required
def task_detail_page(task_id):
    db = get_db()
    row = db.execute(
        '''SELECT t.*, u.username as author_name,
                  m.username as approver_name
           FROM tasks t
           JOIN users u ON u.id = t.author_id
           LEFT JOIN users m ON m.id = t.approved_by
           WHERE t.id=?''',
        (task_id,)
    ).fetchone()
    if not row:
        return render_template('404.html'), 404

    comments = db.execute(
        '''SELECT c.*, u.username as author_name
           FROM comments c JOIN users u ON u.id=c.author_id
           WHERE c.task_id=? ORDER BY c.created_at ASC''',
        (task_id,)
    ).fetchall()

    workflows = db.execute(
        'SELECT * FROM generated_workflows WHERE task_id=? ORDER BY created_at DESC',
        (task_id,)
    ).fetchall()

    return render_template('task_detail.html',
                           task=row,
                           comments=comments,
                           workflows=workflows,
                           user=get_current_user())


@app.route('/admin')
@login_required
@role_required('admin')
def admin_panel():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    audit = recent_events(db, limit=50)
    secrets_meta = db.execute(
        'SELECT id, name, description, owner_team, created_at FROM pipeline_secrets'
    ).fetchall()
    return render_template('admin.html',
                           users=users,
                           audit=audit,
                           secrets_meta=secrets_meta,
                           user=get_current_user())


# ---------------------------------------------------------------------------
# Tasks API
# ---------------------------------------------------------------------------

@app.route('/api/tasks', methods=['GET'])
@login_required
def api_list_tasks():
    db = get_db()
    page, per_page, offset = validate_pagination(request.args)
    status_filter = request.args.get('status')
    author_filter = request.args.get('author_id', type=int)
    label_filter = request.args.get('label')
    rows = list_tasks(db, status=status_filter, author_id=author_filter,
                      label=label_filter, limit=per_page, offset=offset)
    return jsonify(rows)


@app.route('/api/tasks', methods=['POST'])
@login_required
def api_create_task():
    data = request.get_json() or {}
    errors = validate_task_input(data)
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    title = data['title'].strip()
    body = data.get('body', '').strip()
    priority = data.get('priority', 'medium')
    label = data.get('label')
    if label and label not in ALLOWED_LABELS:
        label = None

    db = get_db()
    task_id = create_task(db, title, body, session['user_id'], priority, label)
    log_event(db, session['user_id'], session['username'],
              'task.created', 'tasks', f'task_id={task_id} title={title}',
              get_client_ip())
    return jsonify({'id': task_id, 'title': title, 'status': 'open', 'priority': priority}), 201


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
@login_required
def api_get_task(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)


@app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
@login_required
def api_update_task(task_id):
    """
    Authors may update the title and body of their own tasks.
    Admins may update any task. Updates are allowed at any lifecycle stage
    so that clarifications can be appended after a manager review.
    """
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    user = get_current_user()
    if task['author_id'] != user['id'] and user['role'] != 'admin':
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json() or {}
    new_title = data.get('title', task['title']).strip() or task['title']
    new_body = data.get('body', task['body'])

    if len(new_body) > 20000:
        return jsonify({'error': 'Body exceeds maximum length'}), 400

    # perf: skip re-validation when only whitespace changed
    update_task_body(db, task_id, new_title, new_body)
    log_event(db, user['id'], user['username'],
              'task.updated', 'tasks', f'task_id={task_id}', get_client_ip())
    return jsonify({'id': task_id, 'updated': True})


@app.route('/api/tasks/<int:task_id>/label', methods=['PATCH'])
@login_required
@role_required('manager')
def api_label_task(task_id):
    """
    Managers can classify tasks with a standard label.
    Validates the label against the approved taxonomy before persisting.
    Captures a snapshot of current task metadata for the audit trail.
    """
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json() or {}
    label = data.get('label', '').strip().lower()
    if label not in ALLOWED_LABELS:
        return jsonify({'error': 'Invalid label', 'allowed': sorted(ALLOWED_LABELS)}), 400

    db.execute('UPDATE tasks SET label=?, updated_at=? WHERE id=?',
               (label, datetime.utcnow().isoformat(), task_id))
    db.commit()
    log_event(db, session['user_id'], session['username'],
              'task.labelled', 'tasks',
              f'task_id={task_id} label={label}', get_client_ip())
    return jsonify({'id': task_id, 'label': label})


@app.route('/api/tasks/<int:task_id>/close', methods=['POST'])
@login_required
@role_required('manager')
def api_close_task(task_id):
    """
    Managers can close a task that is no longer relevant.
    Closed tasks are retained for audit purposes.
    """
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['status'] in ('workflow_created', 'closed'):
        return jsonify({'error': f"Cannot close task in '{task['status']}' state"}), 409

    set_task_status(db, task_id, 'closed')
    log_event(db, session['user_id'], session['username'],
              'task.closed', 'tasks', f'task_id={task_id}', get_client_ip())
    return jsonify({'id': task_id, 'status': 'closed'})


@app.route('/api/tasks/<int:task_id>/approve', methods=['POST'])
@login_required
@role_required('manager')
def api_approve_task(task_id):
    """
    Manager reviews and approves a task for AI agent processing.
    Once approved, the agent is queued and will begin processing shortly.
    """
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['status'] != 'open':
        return jsonify({'error': f"Task is not in 'open' state (current: {task['status']})"}), 409

    approve_task(db, task_id, session['user_id'])

    # Notify the task author that their work item was approved
    try:
        notify(db, task['author_id'],
               f"Your task '{task['title']}' was approved by {session['username']} "
               f"and is queued for AI processing.")
    except Exception:
        pass

    log_event(db, session['user_id'], session['username'],
              'task.approved', 'tasks',
              f'task_id={task_id} approver={session["username"]}', get_client_ip())

    # Queue background agent — processing begins after startup delay
    schedule_task_processing(task_id)

    return jsonify({
        'id': task_id,
        'status': 'approved',
        'message': 'AI agent queued for processing'
    })


@app.route('/api/tasks/<int:task_id>/comment', methods=['POST'])
@login_required
def api_add_comment(task_id):
    db = get_db()
    task = get_task(db, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json() or {}
    body = data.get('body', '').strip()
    if not body:
        return jsonify({'error': 'Comment body is required'}), 400
    if len(body) > 5000:
        return jsonify({'error': 'Comment too long'}), 400

    now = datetime.utcnow().isoformat()
    cur = db.execute(
        'INSERT INTO comments (task_id, author_id, body, created_at) VALUES (?,?,?,?)',
        (task_id, session['user_id'], body, now)
    )
    db.commit()
    log_event(db, session['user_id'], session['username'],
              'comment.created', 'comments',
              f'task_id={task_id} comment_id={cur.lastrowid}', get_client_ip())
    return jsonify({'id': cur.lastrowid, 'task_id': task_id, 'created': True}), 201


# ---------------------------------------------------------------------------
# Workflows API
# ---------------------------------------------------------------------------

@app.route('/api/workflows', methods=['GET'])
@login_required
def api_list_workflows():
    db = get_db()
    page, per_page, offset = validate_pagination(request.args)
    task_id_filter = request.args.get('task_id', type=int)
    rows = list_workflows(db, task_id=task_id_filter, limit=per_page, offset=offset)
    return jsonify(rows)


@app.route('/api/workflows/<int:wf_id>', methods=['GET'])
@login_required
def api_get_workflow(wf_id):
    db = get_db()
    wf = get_workflow(db, wf_id)
    if not wf:
        return jsonify({'error': 'Workflow not found'}), 404
    return jsonify(wf)


@app.route('/api/workflows/<int:wf_id>/download', methods=['GET'])
@login_required
def api_download_workflow(wf_id):
    """Return workflow YAML as a downloadable file."""
    db = get_db()
    wf = get_workflow(db, wf_id)
    if not wf:
        return jsonify({'error': 'Workflow not found'}), 404
    from flask import Response
    return Response(
        wf['yaml_content'],
        mimetype='application/x-yaml',
        headers={
            'Content-Disposition': f'attachment; filename="workflow-{wf_id}.yml"'
        }
    )


# ---------------------------------------------------------------------------
# Builds API
# ---------------------------------------------------------------------------

@app.route('/api/builds', methods=['GET'])
@login_required
def api_list_builds():
    db = get_db()
    page, per_page, offset = validate_pagination(request.args)
    rows = db.execute(
        '''SELECT b.*, u.username as triggered_by_name
           FROM builds b JOIN users u ON u.id = b.triggered_by
           ORDER BY b.created_at DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/builds/trigger', methods=['POST'])
@login_required
@role_required('manager')
def api_trigger_build():
    """
    Triggers a CI build run for a generated workflow.
    The workflow content is captured at trigger time; subsequent edits
    to the workflow record do not affect the running build.
    """
    data = request.get_json() or {}
    workflow_id = data.get('workflow_id')
    if not workflow_id:
        return jsonify({'error': 'workflow_id is required'}), 400

    db = get_db()
    wf = get_workflow(db, int(workflow_id))
    if not wf:
        return jsonify({'error': 'Workflow not found'}), 404

    # Snapshot at dispatch time
    snapshot_yaml = wf['yaml_content']
    now = datetime.utcnow().isoformat()

    cur = db.execute(
        '''INSERT INTO builds
           (workflow_id, triggered_by, status, started_at, log_output, created_at)
           VALUES (?,?,?,?,?,?)''',
        (workflow_id, session['user_id'], 'queued', now, '', now)
    )
    build_id = cur.lastrowid
    db.commit()

    def _run_build(bid, content):
        import threading, time
        time.sleep(2)
        conn2 = sqlite3.connect(DATABASE)
        try:
            conn2.execute(
                "UPDATE builds SET status='running', log_output=? WHERE id=?",
                (f'Running workflow ({len(content)} bytes)...', bid)
            )
            conn2.commit()
            time.sleep(3)
            conn2.execute(
                "UPDATE builds SET status='success', finished_at=?, log_output=? WHERE id=?",
                (datetime.utcnow().isoformat(), 'Build completed successfully.', bid)
            )
            conn2.commit()
        finally:
            conn2.close()

    import threading
    threading.Thread(target=_run_build, args=(build_id, snapshot_yaml),
                     daemon=True).start()

    log_event(db, session['user_id'], session['username'],
              'build.triggered', 'builds',
              f'build_id={build_id} workflow_id={workflow_id}', get_client_ip())

    return jsonify({'build_id': build_id, 'status': 'queued', 'workflow_id': workflow_id})


@app.route('/api/builds/<int:build_id>', methods=['GET'])
@login_required
def api_get_build(build_id):
    db = get_db()
    row = db.execute('SELECT * FROM builds WHERE id=?', (build_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Build not found'}), 404
    return jsonify(dict(row))


# ---------------------------------------------------------------------------
# Secrets API (admin only)
# ---------------------------------------------------------------------------

@app.route('/api/secrets', methods=['GET'])
@login_required
@role_required('admin')
def api_list_secrets():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, description, owner_team, created_at, rotated_at FROM pipeline_secrets'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/secrets', methods=['POST'])
@login_required
@role_required('admin')
def api_create_secret():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    value = data.get('value', '').strip()
    description = data.get('description', '').strip()[:255]
    owner_team = data.get('owner_team', 'platform').strip()

    if not name or not value:
        return jsonify({'error': 'name and value are required'}), 400
    if not validate_secret_name(name):
        return jsonify({'error': 'Secret name must be UPPER_SNAKE_CASE, 2-64 chars'}), 400

    db = get_db()
    existing = db.execute(
        'SELECT id FROM pipeline_secrets WHERE name=?', (name,)
    ).fetchone()
    if existing:
        return jsonify({'error': f"Secret '{name}' already exists"}), 409

    now = datetime.utcnow().isoformat()
    db.execute(
        '''INSERT INTO pipeline_secrets
           (name, value, description, owner_team, created_at)
           VALUES (?,?,?,?,?)''',
        (name, value, description, owner_team, now)
    )
    db.commit()
    log_event(db, session['user_id'], session['username'],
              'secret.created', 'pipeline_secrets',
              f'name={name} team={owner_team}', get_client_ip())
    return jsonify({'name': name, 'created': True}), 201


@app.route('/api/secrets/<int:secret_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_delete_secret(secret_id):
    db = get_db()
    row = db.execute('SELECT * FROM pipeline_secrets WHERE id=?', (secret_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Secret not found'}), 404
    db.execute('DELETE FROM pipeline_secrets WHERE id=?', (secret_id,))
    db.commit()
    log_event(db, session['user_id'], session['username'],
              'secret.deleted', 'pipeline_secrets',
              f'name={row["name"]}', get_client_ip())
    return jsonify({'deleted': True, 'name': row['name']})


# ---------------------------------------------------------------------------
# Audit log API
# ---------------------------------------------------------------------------

@app.route('/api/audit', methods=['GET'])
@login_required
@role_required('admin')
def api_audit_log():
    db = get_db()
    page, per_page, offset = validate_pagination(request.args)
    actor = request.args.get('actor')
    action = request.args.get('action')
    events = recent_events(db, limit=per_page, offset=offset,
                           actor_name=actor, action=action)
    return jsonify(events)


# ---------------------------------------------------------------------------
# User profile / notification APIs
# ---------------------------------------------------------------------------

@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
@login_required
def api_user_profile(user_id):
    db = get_db()
    row = db.execute(
        'SELECT id, username, full_name, email, team, role, created_at, last_login FROM users WHERE id=?',
        (user_id,)
    ).fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404
    profile = dict(row)
    task_count = db.execute(
        'SELECT COUNT(*) FROM tasks WHERE author_id=?', (user_id,)
    ).fetchone()[0]
    profile['task_count'] = task_count
    return jsonify(profile)


@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    db = get_db()
    unread = get_unread(db, session['user_id'])
    return jsonify(unread)


@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notif_id):
    db = get_db()
    mark_read(db, session['user_id'], notif_id)
    return jsonify({'read': True})


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------

@app.route('/api/search', methods=['GET'])
@login_required
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400
    db = get_db()
    tasks = db.execute(
        '''SELECT id, title, status, label, created_at
           FROM tasks WHERE title LIKE ? OR body LIKE ?
           ORDER BY created_at DESC LIMIT 20''',
        (f'%{q}%', f'%{q}%')
    ).fetchall()
    workflows = db.execute(
        '''SELECT id, task_id, created_at
           FROM generated_workflows WHERE yaml_content LIKE ?
           ORDER BY created_at DESC LIMIT 10''',
        (f'%{q}%',)
    ).fetchall()
    return jsonify({
        'query': q,
        'tasks': [dict(r) for r in tasks],
        'workflows': [dict(r) for r in workflows],
    })


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('404.html', message='Internal server error'), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)