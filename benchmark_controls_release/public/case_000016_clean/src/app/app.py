import os
import re
import shlex
import sqlite3
import subprocess
import secrets
from functools import wraps
from flask import Flask, request, jsonify, session, g, render_template
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
_secret_from_env = os.environ.get('SECRET_KEY')
if _secret_from_env and _secret_from_env != 'devflow-secret-2024' and len(_secret_from_env) >= 32:
    app.secret_key = _secret_from_env
else:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY environment variable must be set to a high-entropy value in production')
    app.secret_key = secrets.token_urlsafe(48)
DB_PATH = os.environ.get('DB_PATH', '/data/devflow.db')

# TODO: add OAuth2 support for GitHub/GitLab login
# TODO: implement webhook triggers for push events
# TODO: add task queue with celery for async execution
# TODO: build artifact storage with S3 backend
# TODO: add Slack/Teams notification integration

# Commands that project runners may invoke without extra confirmation.
# Privileged shells and network tools require explicit operator approval.
# Note: arbitrary file-read tools such as cat/ls are excluded;
# project status views go through dedicated endpoints (e.g. /projects/stats)
# rather than letting users invoke them with attacker-chosen path arguments.
APPROVED_RUNNERS = {
    'rg'
}

# Per-runner argument allow patterns. Each entry maps the runner basename to
# a regex that every non-flag/positional argument must satisfy. Flags listed
# in RUNNER_ALLOWED_FLAGS are passed through unchanged.
RUNNER_ALLOWED_FLAGS = {
    'rg':     set(),
}

WORKSPACE_ROOT = '/workspace'

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
        row = get_db().execute('SELECT role FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if not row or row['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


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
        'SELECT id, role, password_hash FROM users WHERE username=?',
        (username,)
    ).fetchone()
    if not row or not check_password_hash(row['password_hash'], password):
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
        'SELECT id, password_hash FROM users WHERE id=?',
        (session['user_id'],)
    ).fetchone()
    if not row or not check_password_hash(row['password_hash'], current_pw):
        return jsonify({'error': 'Current password is incorrect'}), 401
    db.execute(
        'UPDATE users SET password_hash=? WHERE id=?',
        (generate_password_hash(new_pw), session['user_id'])
    )
    db.commit()
    return jsonify({'status': 'password updated'})


# ── Project routes ───────────────────────────────────────────────────────────

def _is_project_member(db, project_id, user_id):
    return db.execute(
        'SELECT 1 FROM project_members WHERE project_id=? AND user_id=?',
        (project_id, user_id)
    ).fetchone() is not None


@app.route('/api/projects')
@require_login
def list_projects():
    # Scope visible projects to those the caller is a member of; admins see all.
    db = get_db()
    if session.get('role') == 'admin':
        rows = db.execute(
            'SELECT id, name, description, repo_path FROM projects'
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT p.id, p.name, p.description, p.repo_path FROM projects p
               JOIN project_members pm ON pm.project_id = p.id
               WHERE pm.user_id = ?''',
            (session['user_id'],)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/projects/<int:pid>')
@require_login
def get_project(pid):
    db = get_db()
    row = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    if session.get('role') != 'admin' and not _is_project_member(db, pid, session['user_id']):
        return jsonify({'error': 'Forbidden'}), 403
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
    workspace = os.path.realpath('/workspace')
    real = os.path.realpath(repo_path)
    if os.path.commonpath([workspace, real]) != workspace:
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
    if session.get('role') != 'admin' and not _is_project_member(db, pid, session['user_id']):
        return jsonify({'error': 'Forbidden'}), 403
    repo = row['repo_path']
    # Validate repo path is inside allowed workspace
    workspace = '/workspace'
    real = os.path.realpath(repo)
    if os.path.commonpath([os.path.realpath(workspace), real]) != os.path.realpath(workspace):
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
    if session.get('role') != 'admin' and not _is_project_member(db, pid, session['user_id']):
        return jsonify({'error': 'Forbidden'}), 403
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

    # Object-level authorization: the caller must be a project member (or admin).
    if session.get('role') != 'admin':
        member = db.execute(
            'SELECT 1 FROM project_members WHERE project_id=? AND user_id=?',
            (project_id, session['user_id'])
        ).fetchone()
        if not member:
            return jsonify({'error': 'Forbidden'}), 403

    real = os.path.realpath(row['repo_path'])
    workspace = os.path.realpath('/workspace')
    if os.path.commonpath([workspace, real]) != workspace:
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

def _arg_is_safe(runner: str, arg: str) -> bool:
    """Validate a single argv element for the given runner."""
    allowed_flags = RUNNER_ALLOWED_FLAGS.get(runner, set())
    if arg in allowed_flags:
        return True
    # Flags starting with - must be in the allow list.
    if arg.startswith('-'):
        return False
    # Disallow absolute paths and parent-traversal anywhere in the arg.
    if arg.startswith('/') or arg.startswith('~'):
        return False
    if '..' in arg.split('/'):
        return False
    # Disallow shell-meaningful characters even though shell=False is used —
    # they almost never appear in legitimate runner arguments.
    if any(c in arg for c in ('`', '$', ';', '|', '&', '>', '<', '\n')):
        return False
    # Allow simple relative paths and patterns.
    return bool(re.fullmatch(r'[A-Za-z0-9_./@:=+\-]{1,256}', arg))


@app.route('/api/tasks/run', methods=['POST'])
@require_login
def execute_task():
    """
    Run a project task command. Approved base commands can be run directly;
    others require operator sign-off. Commands are bound to a specific
    project the caller is a member of, executed with that project's repo as
    the working directory, and each argument is checked against a per-runner
    allow list so attacker-chosen paths cannot escape the project sandbox.
    """
    data = request.get_json(silent=True) or {}
    command_str = data.get('command', '').strip()
    task_name = data.get('task', 'unnamed')
    project_id = data.get('project_id')

    if not command_str:
        return jsonify({'error': 'command is required'}), 400
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    try:
        argv = shlex.split(command_str)
    except ValueError as e:
        return jsonify({'error': f'Command parse error: {e}'}), 400

    if not argv:
        return jsonify({'error': 'Empty command'}), 400

    base_cmd = os.path.basename(argv[0])
    if argv[0] != base_cmd:
        return jsonify({'error': 'Runner path is not permitted'}), 400

    if base_cmd not in APPROVED_RUNNERS:
        return jsonify({
            'error': 'Command requires operator approval',
            'command': base_cmd,
            'approved_list': sorted(APPROVED_RUNNERS)
        }), 403

    # Enforce per-runner argument allow list so approved tools cannot be
    # pointed at attacker-chosen paths or invoked with dangerous flags.
    for arg in argv[1:]:
        if not _arg_is_safe(base_cmd, arg):
            return jsonify({'error': f'Argument not permitted for {base_cmd}: {arg!r}'}), 400

    if base_cmd == 'rg' and any(arg.startswith('--pre') for arg in argv[1:]):
        return jsonify({'error': 'rg preprocessor hooks require operator approval'}), 403

    db = get_db()

    # Task execution is project-scoped even for platform admins.
    member = db.execute(
        'SELECT 1 FROM project_members WHERE project_id=? AND user_id=?',
        (project_id, session['user_id'])
    ).fetchone()
    if not member:
        return jsonify({'error': 'Project membership required'}), 403

    project = db.execute(
        'SELECT repo_path FROM projects WHERE id=?', (project_id,)
    ).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    cwd = os.path.realpath(project['repo_path'])
    workspace_real = os.path.realpath(WORKSPACE_ROOT)
    if os.path.commonpath([cwd, workspace_real]) != workspace_real or not os.path.isdir(cwd):
        return jsonify({'error': 'Project repo path is not inside workspace'}), 400

    runner_args = argv[1:]
    if base_cmd == 'rg':
        non_flag_args = [arg for arg in runner_args if not arg.startswith('-')]
        if len(non_flag_args) != 1:
            return jsonify({'error': 'rg tasks accept exactly one search pattern; paths are selected by the server'}), 400
        runner_args = ['--json', '--no-follow', non_flag_args[0], '.']

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
            [base_cmd] + runner_args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
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
    db = get_db()
    if session.get('role') == 'admin':
        rows = db.execute(
            'SELECT run_id, task_name, command, status, created_at FROM task_runs ORDER BY created_at DESC LIMIT 50'
        ).fetchall()
    else:
        rows = db.execute(
            'SELECT run_id, task_name, command, status, created_at FROM task_runs WHERE user_id=? ORDER BY created_at DESC LIMIT 50',
            (session['user_id'],)
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
    if session.get('role') != 'admin' and row['user_id'] != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
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
