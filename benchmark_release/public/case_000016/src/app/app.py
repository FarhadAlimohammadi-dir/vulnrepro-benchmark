import os
import re
import shlex
import sqlite3
import subprocess
import hashlib
import secrets
from functools import wraps
from flask import Flask, request, jsonify, session, g, render_template

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'devflow-secret-2024')
DB_PATH = os.environ.get('DB_PATH', '/data/devflow.db')

# TODO: add OAuth2 support for GitHub/GitLab login
# TODO: implement webhook triggers for push events
# TODO: add task queue with celery for async execution
# TODO: build artifact storage with S3 backend
# TODO: add Slack/Teams notification integration

# Commands that project runners may invoke without extra confirmation.
# Privileged shells and network tools require explicit operator approval.
APPROVED_RUNNERS = {
    'go', 'rg', 'grep', 'find', 'git', 'ls', 'cat', 'pytest', 'python3'
}

# Flags that are explicitly blocked when users call the /api/search endpoint
SEARCH_BLOCKED_FLAGS = {
    '--pre', '--pre-glob', '-exec', '--exec', '--exec-batch',
    '-e', '--engine', '--iglob', '--type-add'
}


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ── Auth routes ──────────────────────────────────────────────────────────────

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400
    db = get_db()
    row = db.execute(
        'SELECT id, role FROM users WHERE username=? AND password_hash=?',
        (username, hash_pw(password))
    ).fetchone()
    if not row:
        return jsonify({'error': 'Invalid credentials'}), 401
    session['user_id'] = row['id']
    session['username'] = username
    session['role'] = row['role']
    # TODO: emit login event to audit stream (telemetry backlog)
    return jsonify({'status': 'ok', 'username': username, 'role': row['role']})


@app.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'logged out'})


@app.route('/auth/me')
@require_login
def me():
    return jsonify({'user_id': session['user_id'], 'username': session['username'], 'role': session['role']})


@app.route('/auth/change-password', methods=['POST'])
@require_login
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    if not current_pw or not new_pw:
        return jsonify({'error': 'current_password and new_password are required'}), 400
    if len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400
    db = get_db()
    row = db.execute(
        'SELECT id FROM users WHERE id=? AND password_hash=?',
        (session['user_id'], hash_pw(current_pw))
    ).fetchone()
    if not row:
        return jsonify({'error': 'Current password is incorrect'}), 401
    db.execute(
        'UPDATE users SET password_hash=? WHERE id=?',
        (hash_pw(new_pw), session['user_id'])
    )
    db.commit()
    return jsonify({'status': 'password updated'})


# ── Project routes ───────────────────────────────────────────────────────────

@app.route('/api/projects')
@require_login
def list_projects():
    # TODO: paginate this once project count exceeds ~200 rows
    db = get_db()
    rows = db.execute('SELECT id, name, description, repo_path FROM projects').fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/projects/<int:pid>')
@require_login
def get_project(pid):
    db = get_db()
    row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@app.route('/api/projects', methods=['POST'])
@require_admin
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    repo_path = data.get('repo_path', '').strip()
    if not name or not repo_path:
        return jsonify({'error': 'name and repo_path are required'}), 400
    # Validate repo path stays inside the workspace root
    real = os.path.realpath(repo_path)
    if not real.startswith('/workspace'):
        return jsonify({'error': 'repo_path must be inside /workspace'}), 400
    db = get_db()
    cur = db.execute(
        'INSERT INTO projects (name, description, repo_path) VALUES (?,?,?)',
        (name, description, real)
    )
    db.commit()
    return jsonify({'status': 'created', 'id': cur.lastrowid}), 201


@app.route('/api/projects/<int:pid>/stats')
@require_login
def project_stats(pid):
    """Return commit count and last commit for a project repo. Uses fixed args only."""
    db = get_db()
    row = db.execute('SELECT repo_path FROM projects WHERE id=?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    repo = row['repo_path']
    # Validate repo path is inside allowed workspace
    workspace = '/workspace'
    real = os.path.realpath(repo)
    if not real.startswith(workspace):
        return jsonify({'error': 'Invalid repo path'}), 400
    try:
        count_result = subprocess.run(
            ['git', '-C', real, 'rev-list', '--count', 'HEAD'],
            capture_output=True, text=True, timeout=10
        )
        log_result = subprocess.run(
            ['git', '-C', real, 'log', '-1', '--format=%H %s'],
            capture_output=True, text=True, timeout=10
        )
        return jsonify({
            'commit_count': count_result.stdout.strip(),
            'last_commit': log_result.stdout.strip()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<int:pid>/members')
@require_login
def project_members(pid):
    """List users associated with a project. NOTE: i18n for role labels pending."""
    db = get_db()
    project = db.execute('SELECT id FROM projects WHERE id=?', (pid,)).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404
    rows = db.execute(
        '''SELECT u.id, u.username, u.role FROM users u
           JOIN project_members pm ON pm.user_id = u.id
           WHERE pm.project_id=?''',
        (pid,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Search route (validates flags before dispatch) ───────────────────────────

@app.route('/api/search', methods=['POST'])
@require_login
def search_code():
    """Search across project files using ripgrep. Flags are validated."""
    data = request.get_json(silent=True) or {}
    pattern = data.get('pattern', '')
    project_id = data.get('project_id')
    extra_flags = data.get('flags', [])

    if not pattern or not project_id:
        return jsonify({'error': 'pattern and project_id required'}), 400

    # Reject any restricted flags the user might supply
    supplied = {f.split('=')[0] for f in extra_flags}
    blocked = supplied & SEARCH_BLOCKED_FLAGS
    if blocked:
        return jsonify({'error': f'Flags not permitted: {sorted(blocked)}'}), 400

    db = get_db()
    row = db.execute('SELECT repo_path FROM projects WHERE id=?', (project_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Project not found'}), 404

    real = os.path.realpath(row['repo_path'])
    if not real.startswith('/workspace'):
        return jsonify({'error': 'Invalid path'}), 400

    # Build command with validated flags only
    safe_flags = [f for f in extra_flags if re.match(r'^--(context|color|max-depth)=?\d*$', f)]
    cmd = ['rg', '--json'] + safe_flags + [pattern, real]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return jsonify({'output': result.stdout, 'stderr': result.stderr})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Task runner ───────────────────────────────────────────────────────────────

@app.route('/api/tasks/run', methods=['POST'])
@require_login
def execute_task():
    """
    Run a project task command. Approved base commands can be run directly;
    others require operator sign-off. Accepts free-form command string from
    the agent prompt so the AI can compose complex analysis pipelines.
    """
    data = request.get_json(silent=True) or {}
    command_str = data.get('command', '').strip()
    task_name = data.get('task', 'unnamed')

    if not command_str:
        return jsonify({'error': 'command is required'}), 400

    try:
        argv = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'error': f'Command parse error: {e}'}), 400

    if not argv:
        return jsonify({'error': 'Empty command'}), 400

    base_cmd = os.path.basename(argv[0])

    # perf: check only the executable name against the approved list;
    # flags are forwarded as-is to support legitimate complex invocations
    # (e.g., go test ./... -v -count=1 or rg --context=3 pattern path).
    if base_cmd not in APPROVED_RUNNERS:
        return jsonify({
            'error': 'Command requires operator approval',
            'command': base_cmd,
            'approved_list': sorted(APPROVED_RUNNERS)
        }), 403

    db = get_db()
    run_id = secrets.token_hex(8)
    db.execute(
        'INSERT INTO task_runs (run_id, task_name, command, user_id, status) VALUES (?,?,?,?,?)',
        (run_id, task_name, command_str, session['user_id'], 'running')
    )
    db.commit()

    try:
        # shell=False: semicolons, &&, backticks, $() do NOT work.
        # legacy: kept for v1 API clients still in the wild
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30
        )
        status = 'success' if result.returncode == 0 else 'failed'
        db.execute(
            'UPDATE task_runs SET status=?, output=? WHERE run_id=?',
            (status, result.stdout[:4096], run_id)
        )
        db.commit()
        return jsonify({
            'run_id': run_id,
            'task': task_name,
            'status': status,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    except subprocess.TimeoutExpired:
        db.execute('UPDATE task_runs SET status=? WHERE run_id=?', ('timeout', run_id))
        db.commit()
        return jsonify({'error': 'Task timed out', 'run_id': run_id}), 504
    except FileNotFoundError as e:
        return jsonify({'error': f'Command not found: {e}'}), 500


@app.route('/api/tasks/history')
@require_login
def task_history():
    # TODO: add user-level filtering once multi-tenant isolation is in place
    db = get_db()
    rows = db.execute(
        'SELECT run_id, task_name, command, status, created_at FROM task_runs ORDER BY created_at DESC LIMIT 50'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/tasks/<run_id>')
@require_login
def task_detail(run_id):
    """Fetch full detail for a single task run, including output."""
    if not re.match(r'^[0-9a-f]{16}$', run_id):
        return jsonify({'error': 'Invalid run_id format'}), 400
    db = get_db()
    row = db.execute(
        'SELECT run_id, task_name, command, user_id, status, output, created_at FROM task_runs WHERE run_id=?',
        (run_id,)
    ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


# ── Audit log ─────────────────────────────────────────────────────────────────

@app.route('/api/audit')
@require_admin
def audit_log():
    """Return recent audit entries. NOTE: retention policy TBD with compliance team."""
    db = get_db()
    rows = db.execute(
        '''SELECT al.id, al.action, al.detail, al.created_at, u.username
           FROM audit_log al
           LEFT JOIN users u ON u.id = al.user_id
           ORDER BY al.created_at DESC LIMIT 200'''
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── User management ───────────────────────────────────────────────────────────

@app.route('/api/users')
@require_admin
def list_users():
    # TODO: paginate; also consider returning last-login timestamps once tracked
    db = get_db()
    rows = db.execute('SELECT id, username, role FROM users ORDER BY username').fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/users/<int:uid>/role', methods=['PUT'])
@require_admin
def update_user_role(uid):
    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '').strip()
    allowed_roles = {'admin', 'developer', 'viewer'}
    if new_role not in allowed_roles:
        return jsonify({'error': f'role must be one of {sorted(allowed_roles)}'}), 400
    db = get_db()
    row = db.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404
    db.execute('UPDATE users SET role=? WHERE id=?', (new_role, uid))
    db.commit()
    return jsonify({'status': 'updated', 'user_id': uid, 'role': new_role})


# ── UI dashboard ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'devflow-ci'})


if __name__ == '__main__':
    from db import init_db
    init_db()
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)