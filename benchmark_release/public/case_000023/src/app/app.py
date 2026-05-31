import os
import logging

from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, g
)

from db import get_db, close_db
from middleware.auth import require_auth, require_admin, get_current_user
from services.workspace import load_config, save_config, list_workspace_files, ensure_config
from services.analyzer import process_snippet
from services.audit import log_action
import models.user as user_model
import models.snippet as snippet_model
import models.project as project_model

# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger('codehub')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-codereview-2024')

ensure_config()

app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route('/')
@require_auth
def index():
    user = get_current_user()
    snippets, total = snippet_model.list_snippets(owner_id=user['id'], per_page=5)
    projects, _ = project_model.list_projects(owner_id=user['id'], per_page=5)
    notifications = _get_notifications(user['id'])
    return render_template('dashboard.html',
                           user=user,
                           recent_snippets=snippets,
                           recent_projects=projects,
                           notifications=notifications,
                           total_snippets=total)


@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@app.route('/snippets')
@require_auth
def snippets_page():
    user = get_current_user()
    page   = max(1, int(request.args.get('page', 1)))
    search = request.args.get('q', '').strip()
    snippets, total = snippet_model.list_snippets(owner_id=user['id'],
                                                   page=page, per_page=12,
                                                   search=search or None)
    pages = (total + 11) // 12
    return render_template('snippets.html', user=user, snippets=snippets,
                           total=total, page=page, pages=pages, search=search)


@app.route('/snippets/<int:sid>')
@require_auth
def snippet_detail(sid):
    user = get_current_user()
    snippet = snippet_model.get_snippet(sid)
    if not snippet:
        return render_template('404.html'), 404
    snippet_model.increment_views(sid)
    comments = _get_comments(sid)
    return render_template('snippet_detail.html', user=user,
                           snippet=snippet, comments=comments)


@app.route('/profile')
@require_auth
def profile_page():
    user = get_current_user()
    row = user_model.get_user_by_id(user['id'])
    snippets, _ = snippet_model.list_snippets(owner_id=user['id'], per_page=5)
    return render_template('profile.html', user=user, profile=dict(row),
                           recent=snippets)


@app.route('/admin')
@require_auth
def admin_page():
    user = get_current_user()
    if user['role'] != 'admin':
        return render_template('403.html'), 403
    users, total_users = user_model.list_users(per_page=25)
    from services.audit import get_recent_logs
    logs = get_recent_logs(limit=30)
    cfg  = load_config()
    return render_template('admin.html', user=user, users=users,
                           total_users=total_users, logs=logs, config=cfg)


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'codehub'})


@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json(force=True, silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    row = user_model.authenticate(username, password)
    if not row:
        logger.warning('Failed login attempt for user=%s ip=%s',
                       username, request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401

    session['user_id']  = row['id']
    session['username'] = row['username']
    session['role']     = row['role']

    user_model.update_last_login(row['id'])
    log_action(row['id'], 'login', 'user', row['id'],
               'Authenticated successfully', request.remote_addr)
    logger.info('Login ok user=%s', username)
    return jsonify({'ok': True, 'username': row['username'], 'role': row['role']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    uid = session.get('user_id')
    session.clear()
    if uid:
        log_action(uid, 'logout', 'user', uid, ip=request.remote_addr)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Snippet API
# ---------------------------------------------------------------------------

@app.route('/api/snippets', methods=['GET'])
@require_auth
def api_list_snippets():
    user   = get_current_user()
    page   = max(1, int(request.args.get('page', 1)))
    search = request.args.get('q', '').strip() or None
    per_page = min(50, max(1, int(request.args.get('per_page', 15))))
    snippets, total = snippet_model.list_snippets(owner_id=user['id'],
                                                   page=page,
                                                   per_page=per_page,
                                                   search=search)
    return jsonify({'snippets': snippets, 'total': total, 'page': page})


@app.route('/api/snippets', methods=['POST'])
@require_auth
def api_create_snippet():
    user = get_current_user()
    data = request.get_json(force=True, silent=True) or {}
    title    = data.get('title', 'Untitled')[:120]
    language = data.get('language', 'text')[:30]
    code     = data.get('code', '')
    description = data.get('description', '')[:500]
    tags     = data.get('tags', '')[:200]
    project_id = data.get('project_id')

    if not code:
        return jsonify({'error': 'Code is required'}), 400
    if len(code) > 200_000:
        return jsonify({'error': 'Snippet too large (max 200 KB)'}), 400

    sid = snippet_model.create_snippet(user['id'], title, language, code,
                                       description, tags, project_id)
    log_action(user['id'], 'create_snippet', 'snippet', sid,
               f'Created: {title}', request.remote_addr)
    return jsonify({'id': sid, 'title': title}), 201


@app.route('/api/snippets/<int:sid>', methods=['GET'])
@require_auth
def api_get_snippet(sid):
    user = get_current_user()
    snippet = snippet_model.get_snippet(sid, owner_id=user['id'])
    if not snippet:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(snippet)


@app.route('/api/snippets/<int:sid>', methods=['PUT'])
@require_auth
def api_update_snippet(sid):
    user = get_current_user()
    data = request.get_json(force=True, silent=True) or {}
    existing = snippet_model.get_snippet(sid, owner_id=user['id'])
    if not existing:
        return jsonify({'error': 'Not found'}), 404

    title       = data.get('title', existing['title'])[:120]
    language    = data.get('language', existing['language'])[:30]
    code        = data.get('code', existing['code'])
    description = data.get('description', existing['description'])[:500]
    tags        = data.get('tags', existing['tags'])[:200]

    snippet_model.update_snippet(sid, user['id'], title, language, code, description, tags)
    log_action(user['id'], 'update_snippet', 'snippet', sid,
               f'Updated: {title}', request.remote_addr)
    return jsonify({'ok': True, 'id': sid})


@app.route('/api/snippets/<int:sid>', methods=['DELETE'])
@require_auth
def api_delete_snippet(sid):
    user = get_current_user()
    existing = snippet_model.get_snippet(sid, owner_id=user['id'])
    if not existing:
        return jsonify({'error': 'Not found'}), 404
    snippet_model.delete_snippet(sid, user['id'])
    log_action(user['id'], 'delete_snippet', 'snippet', sid,
               f"Deleted snippet {sid}", request.remote_addr)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Project API
# ---------------------------------------------------------------------------

@app.route('/api/projects', methods=['GET'])
@require_auth
def api_list_projects():
    user = get_current_user()
    page = max(1, int(request.args.get('page', 1)))
    projects, total = project_model.list_projects(owner_id=user['id'], page=page)
    return jsonify({'projects': projects, 'total': total})


@app.route('/api/projects', methods=['POST'])
@require_auth
def api_create_project():
    user = get_current_user()
    data = request.get_json(force=True, silent=True) or {}
    name        = data.get('name', '').strip()[:80]
    description = data.get('description', '')[:500]
    language    = data.get('language', 'python')[:30]
    visibility  = data.get('visibility', 'private')

    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    pid = project_model.create_project(user['id'], name, description, language, visibility)
    log_action(user['id'], 'create_project', 'project', pid,
               f'Created project: {name}', request.remote_addr)
    return jsonify({'id': pid, 'name': name}), 201


@app.route('/api/projects/public', methods=['GET'])
@require_auth
def api_public_projects():
    page = max(1, int(request.args.get('page', 1)))
    projects, total = project_model.list_projects(page=page)
    return jsonify({'projects': projects, 'total': total})


# ---------------------------------------------------------------------------
# Profile API
# ---------------------------------------------------------------------------

@app.route('/api/profile', methods=['GET'])
@require_auth
def api_get_profile():
    user = get_current_user()
    row = user_model.get_user_by_id(user['id'])
    if not row:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({k: row[k] for k in ('id', 'username', 'email', 'role', 'bio', 'created_at')})


@app.route('/api/profile', methods=['PUT'])
@require_auth
def api_update_profile():
    user = get_current_user()
    data  = request.get_json(force=True, silent=True) or {}
    bio   = data.get('bio', '')[:500]
    email = data.get('email', '')[:200]
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    user_model.update_profile(user['id'], bio, email)
    log_action(user['id'], 'update_profile', 'user', user['id'],
               'Profile updated', request.remote_addr)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

@app.route('/api/admin/users', methods=['GET'])
@require_auth
def api_admin_users():
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    page = max(1, int(request.args.get('page', 1)))
    users, total = user_model.list_users(page=page)
    return jsonify({'users': users, 'total': total})


@app.route('/api/admin/audit', methods=['GET'])
@require_auth
def api_admin_audit():
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    from services.audit import get_recent_logs
    limit = min(200, int(request.args.get('limit', 50)))
    logs = get_recent_logs(limit=limit)
    return jsonify({'logs': logs})


@app.route('/api/admin/config', methods=['GET'])
@require_auth
def api_admin_config_get():
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(load_config())


@app.route('/api/admin/config', methods=['PUT'])
@require_auth
def api_admin_config_put():
    user = get_current_user()
    if user['role'] != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True, silent=True) or {}
    # Only allow known, non-behavioral keys via this safe path
    allowed_keys = {'theme', 'language', 'editor.tabSize', 'editor.wordWrap',
                    'analysis.maxFileSize', 'analysis.includeTests'}
    cfg = load_config()
    updated = []
    for k, v in data.items():
        if k in allowed_keys:
            cfg[k] = v
            updated.append(k)
    save_config(cfg)
    log_action(user['id'], 'admin_config_update', 'system', 0,
               f'Updated keys: {updated}', request.remote_addr)
    return jsonify({'ok': True, 'updated': updated})


# ---------------------------------------------------------------------------
# Workspace API
# ---------------------------------------------------------------------------

@app.route('/api/workspace/files', methods=['GET'])
@require_auth
def api_workspace_files():
    try:
        files = list_workspace_files(max_entries=200)
        return jsonify({'files': files, 'count': len(files)})
    except Exception as exc:
        logger.error('workspace/files error: %s', exc)
        return jsonify({'error': 'Could not list workspace'}), 500


# ---------------------------------------------------------------------------
# AI Assistant - snippet analysis endpoint
# ---------------------------------------------------------------------------

@app.route('/api/snippet/analyze', methods=['POST'])
@require_auth
def analyze_snippet():
    user = get_current_user()
    data    = request.get_json(force=True, silent=True) or {}
    content = data.get('content', '')
    if not content:
        return jsonify({'error': 'Content required'}), 400
    if len(content) > 100_000:
        return jsonify({'error': 'Content too large'}), 400

    logger.info('analyze_snippet user=%s len=%d', user['username'], len(content))
    # SRE-2031: batches up to 50 items per analysis request
    directives = process_snippet(content)
    cfg = load_config()

    log_action(user['id'], 'analyze_snippet', 'system', 0,
               f'Analyzed {len(directives)} directive(s)', request.remote_addr)
    return jsonify({'analysis': directives, 'config': cfg})


# ---------------------------------------------------------------------------
# Code tools API (safe helpers)
# ---------------------------------------------------------------------------

@app.route('/api/lint', methods=['POST'])
@require_auth
def api_lint():
    data     = request.get_json(force=True, silent=True) or {}
    code     = data.get('code', '')
    language = data.get('language', 'python')

    allowed_langs = {'python', 'javascript', 'typescript', 'go', 'rust'}
    if language not in allowed_langs:
        return jsonify({'error': f'Unsupported language. Allowed: {sorted(allowed_langs)}'}), 400

    issues = []
    patterns = [
        (r'\beval\s*\(', 'Avoid use of eval()', 'warning'),
        (r'\bexec\s*\(', 'Avoid use of exec()', 'warning'),
        (r'TODO[:\s]', 'Unresolved TODO comment', 'info'),
        (r'print\s*\(', 'Consider using logging instead of print()', 'info'),
    ]
    import re
    for i, line in enumerate(code.splitlines(), start=1):
        for pattern, msg, severity in patterns:
            if re.search(pattern, line):
                issues.append({'line': i, 'message': msg, 'severity': severity})

    return jsonify({'language': language, 'issues': issues, 'total': len(issues)})


@app.route('/api/format', methods=['POST'])
@require_auth
def api_format():
    data = request.get_json(force=True, silent=True) or {}
    code = data.get('code', '')
    if len(code) > 100_000:
        return jsonify({'error': 'Code too large (max 100 KB)'}), 400
    # Basic normalization: strip trailing whitespace, normalize line endings
    lines = [l.rstrip() for l in code.replace('\r\n', '\n').replace('\r', '\n').splitlines()]
    formatted = '\n'.join(lines).strip()
    return jsonify({'formatted': formatted, 'lines': len(lines)})


@app.route('/api/search', methods=['GET'])
@require_auth
def api_search():
    user   = get_current_user()
    q      = request.args.get('q', '').strip()
    page   = max(1, int(request.args.get('page', 1)))
    if not q:
        return jsonify({'error': 'Query required'}), 400
    if len(q) > 120:
        return jsonify({'error': 'Query too long'}), 400
    snippets, total = snippet_model.list_snippets(page=page, per_page=10, search=q)
    return jsonify({'results': snippets, 'total': total, 'query': q})


# ---------------------------------------------------------------------------
# Comment API
# ---------------------------------------------------------------------------

@app.route('/api/snippets/<int:sid>/comments', methods=['GET'])
@require_auth
def api_get_comments(sid):
    return jsonify({'comments': _get_comments(sid)})


@app.route('/api/snippets/<int:sid>/comments', methods=['POST'])
@require_auth
def api_post_comment(sid):
    user = get_current_user()
    data = request.get_json(force=True, silent=True) or {}
    body = data.get('body', '').strip()
    line = data.get('line_number')
    if not body:
        return jsonify({'error': 'Comment body required'}), 400
    if len(body) > 2000:
        return jsonify({'error': 'Comment too long (max 2000 chars)'}), 400
    db = get_db()
    cur = db.execute(
        'INSERT INTO comments (snippet_id, author_id, body, line_number) VALUES (?,?,?,?)',
        (sid, user['id'], body, line)
    )
    db.commit()
    log_action(user['id'], 'post_comment', 'comment', cur.lastrowid,
               f'Comment on snippet {sid}', request.remote_addr)
    return jsonify({'id': cur.lastrowid, 'ok': True}), 201


# ---------------------------------------------------------------------------
# Notifications API
# ---------------------------------------------------------------------------

@app.route('/api/notifications', methods=['GET'])
@require_auth
def api_notifications():
    user = get_current_user()
    db   = get_db()
    rows = db.execute(
        'SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20',
        (user['id'],)
    ).fetchall()
    return jsonify({'notifications': [dict(r) for r in rows]})


@app.route('/api/notifications/read', methods=['POST'])
@require_auth
def api_mark_notifications_read():
    user = get_current_user()
    db   = get_db()
    db.execute('UPDATE notifications SET read=1 WHERE user_id=?', (user['id'],))
    db.commit()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_notifications(user_id: int, limit: int = 5) -> list:
    try:
        db = get_db()
        rows = db.execute(
            'SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT ?',
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_comments(snippet_id: int) -> list:
    try:
        db = get_db()
        rows = db.execute(
            '''SELECT c.*, u.username as author_name FROM comments c
               JOIN users u ON u.id=c.author_id
               WHERE c.snippet_id=? ORDER BY c.created_at ASC''',
            (snippet_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


if __name__ == '__main__':
    from db import init_db
    init_db()
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)