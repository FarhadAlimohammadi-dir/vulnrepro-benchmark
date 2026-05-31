import logging
import json
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, g, jsonify, abort
)
from routes.auth import login_required
from database import (
    create_workspace, get_workspace, get_workspaces_for_user,
    update_workspace_status, update_workspace_config, update_workspace,
    delete_workspace,
    is_workspace_member, get_workspace_members, add_workspace_member,
    remove_workspace_member,
    get_user_by_username, write_audit,
    get_review_sessions, create_review_session,
    create_notification,
)
from services.workspace_service import (
    build_workspace_context,
    activate_workspace_environment,
    import_repository_config,
    get_lint_result,
    get_format_result,
    compute_config_checksum,
)

logger = logging.getLogger('codenest.workspaces')
bp = Blueprint('workspaces', __name__, url_prefix='/workspaces')

VALID_VISIBILITIES = ('private', 'team', 'public')
VALID_LANGUAGES = ('python', 'javascript', 'typescript', 'go', 'rust',
                   'ruby', 'java', 'hcl', 'markdown', 'other')


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@bp.route('/')
@login_required
def list_workspaces():
    page = int(request.args.get('page', 1))
    q = request.args.get('q', '').strip()
    workspaces, total = get_workspaces_for_user(g.user['id'], page=page, per_page=12)
    if q:
        workspaces = [w for w in workspaces if q.lower() in w['name'].lower()
                      or q.lower() in (w.get('description') or '').lower()]
    total_pages = max(1, (total + 11) // 12)
    return render_template(
        'workspaces/list.html',
        user=g.user, workspaces=workspaces,
        page=page, total_pages=total_pages, total=total, q=q,
    )


@bp.route('/<int:ws_id>')
@login_required
def detail(ws_id):
    ws = _get_accessible_workspace(ws_id)
    context = build_workspace_context(ws)
    members = get_workspace_members(ws_id)
    sessions = get_review_sessions(ws_id, limit=10)
    return render_template(
        'workspaces/detail.html',
        user=g.user, ws=ws, context=context,
        members=members, sessions=sessions,
    )


@bp.route('/<int:ws_id>/settings', methods=['GET', 'POST'])
@login_required
def settings(ws_id):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin',) and g.user['role'] != 'admin':
        return render_template('error.html', code=403, message='Admin access required'), 403

    error = None
    success = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        visibility = request.form.get('visibility', 'private')
        language = request.form.get('language', 'python')

        if not name or len(name) < 3:
            error = 'Workspace name must be at least 3 characters'
        elif visibility not in VALID_VISIBILITIES:
            error = 'Invalid visibility setting'
        elif language not in VALID_LANGUAGES:
            error = 'Invalid language'
        else:
            update_workspace(ws_id, name, description, visibility, language)
            write_audit(g.user['id'], 'workspace_updated', 'workspace', ws_id,
                       {'name': name, 'visibility': visibility}, ip=request.remote_addr)
            success = 'Workspace settings saved'
            ws = get_workspace(ws_id)

    return render_template('workspaces/settings.html',
                           user=g.user, ws=ws, error=error, success=success,
                           valid_visibilities=VALID_VISIBILITIES,
                           valid_languages=VALID_LANGUAGES)


@bp.route('/<int:ws_id>/delete', methods=['POST'])
@login_required
def delete(ws_id):
    ws = _get_accessible_workspace(ws_id)
    if ws['owner_id'] != g.user['id'] and g.user['role'] != 'admin':
        return jsonify({'error': 'Only the workspace owner can delete it'}), 403
    delete_workspace(ws_id)
    write_audit(g.user['id'], 'workspace_deleted', 'workspace', ws_id,
               {'name': ws['name']}, ip=request.remote_addr)
    return redirect(url_for('workspaces.list_workspaces'))


# ---------------------------------------------------------------------------
# REST API  (/workspaces/api/*)
# ---------------------------------------------------------------------------

@bp.route('/api/workspaces', methods=['GET'])
@login_required
def api_list():
    page = int(request.args.get('page', 1))
    workspaces, total = get_workspaces_for_user(g.user['id'], page=page, per_page=20)
    return jsonify({
        'workspaces': [_serialize_workspace(w) for w in workspaces],
        'total': total,
        'page': page,
    })


@bp.route('/api/workspaces', methods=['POST'])
@login_required
def api_create():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    visibility = data.get('visibility', 'private')
    workspace_config = data.get('workspace_config', {})
    language = data.get('language', 'python')

    errors = []
    if not name or len(name) < 3:
        errors.append('name must be at least 3 characters')
    if len(name) > 80:
        errors.append('name must be 80 characters or fewer')
    if visibility not in VALID_VISIBILITIES:
        errors.append(f'visibility must be one of {VALID_VISIBILITIES}')
    if not isinstance(workspace_config, dict):
        errors.append('workspace_config must be a JSON object')
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    # Infer language from config if not top-level
    if language not in VALID_LANGUAGES:
        language = workspace_config.get('language', 'python')
        if language not in VALID_LANGUAGES:
            language = 'other'

    ws_id = create_workspace(
        name=name,
        description=description,
        owner_id=g.user['id'],
        visibility=visibility,
        workspace_config=workspace_config,
        language=language,
    )
    write_audit(g.user['id'], 'workspace_created', 'workspace', ws_id,
               {'name': name, 'visibility': visibility}, ip=request.remote_addr)
    ws = get_workspace(ws_id)
    return jsonify({'id': ws_id, 'workspace': _serialize_workspace(ws)}), 201


@bp.route('/api/workspaces/<int:ws_id>', methods=['GET'])
@login_required
def api_get(ws_id):
    ws = _get_accessible_workspace(ws_id)
    return jsonify(_serialize_workspace(ws))


@bp.route('/api/workspaces/<int:ws_id>', methods=['PATCH'])
@login_required
def api_update(ws_id):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin',) and g.user['role'] != 'admin':
        return jsonify({'error': 'Admin workspace role required'}), 403

    data = request.get_json(silent=True) or {}
    name = data.get('name', ws['name']).strip()
    description = data.get('description', ws.get('description', ''))
    visibility = data.get('visibility', ws['visibility'])
    language = data.get('language', ws.get('language', 'python'))

    if visibility not in VALID_VISIBILITIES:
        return jsonify({'error': 'Invalid visibility'}), 400

    update_workspace(ws_id, name, description, visibility, language)
    write_audit(g.user['id'], 'workspace_patched', 'workspace', ws_id,
               {'name': name}, ip=request.remote_addr)
    return jsonify(_serialize_workspace(get_workspace(ws_id)))


@bp.route('/api/workspaces/<int:ws_id>', methods=['DELETE'])
@login_required
def api_delete(ws_id):
    ws = _get_accessible_workspace(ws_id)
    if ws['owner_id'] != g.user['id'] and g.user['role'] != 'admin':
        return jsonify({'error': 'Only workspace owner can delete'}), 403
    delete_workspace(ws_id)
    write_audit(g.user['id'], 'workspace_deleted', 'workspace', ws_id,
               {'name': ws['name']}, ip=request.remote_addr)
    return jsonify({'deleted': True, 'id': ws_id})


@bp.route('/api/workspaces/<int:ws_id>/activate', methods=['POST'])
@login_required
def api_activate(ws_id):
    """
    Transition a workspace from idle to active.

    Validates membership, runs environment bootstrap (including MCP server
    initialization), and records the activation event in the audit log.
    """
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if not member_role:
        return jsonify({'error': 'Access denied'}), 403

    if ws['status'] == 'active':
        return jsonify({'message': 'Workspace already active', 'workspace_id': ws_id}), 200

    logger.info('Workspace activation requested: id=%d by user=%d', ws_id, g.user['id'])

    summary = activate_workspace_environment(ws)

    import json as _json
    update_workspace_status(ws_id, 'active', activation_log=_json.dumps(summary))
    write_audit(g.user['id'], 'workspace_activated', 'workspace', ws_id,
               {'mcp_count': len(summary.get('mcp_bootstrap', []))},
               ip=request.remote_addr)

    create_notification(
        ws['owner_id'],
        f'Workspace "{ws["name"]}" is now active',
        f'Activated by {g.user["username"]}'
    )

    return jsonify({'status': 'active', 'workspace_id': ws_id, 'summary': summary})


@bp.route('/api/workspaces/<int:ws_id>/deactivate', methods=['POST'])
@login_required
def api_deactivate(ws_id):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if not member_role:
        return jsonify({'error': 'Access denied'}), 403
    update_workspace_status(ws_id, 'idle')
    write_audit(g.user['id'], 'workspace_deactivated', 'workspace', ws_id,
               ip=request.remote_addr)
    return jsonify({'status': 'idle', 'workspace_id': ws_id})


@bp.route('/api/workspaces/<int:ws_id>/config', methods=['GET'])
@login_required
def api_get_config(ws_id):
    ws = _get_accessible_workspace(ws_id)
    cfg = ws.get('workspace_config', {})
    checksum = compute_config_checksum(cfg)
    return jsonify({'workspace_id': ws_id, 'config': cfg, 'checksum': checksum})


@bp.route('/api/workspaces/<int:ws_id>/config', methods=['PUT'])
@login_required
def api_update_config(ws_id):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin',) and g.user['role'] != 'admin':
        return jsonify({'error': 'Admin workspace role required'}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON object required'}), 400

    update_workspace_config(ws_id, data)
    write_audit(g.user['id'], 'workspace_config_updated', 'workspace', ws_id,
               ip=request.remote_addr)
    return jsonify({'ok': True, 'checksum': compute_config_checksum(data)})


@bp.route('/api/workspaces/<int:ws_id>/members', methods=['GET'])
@login_required
def api_members(ws_id):
    _get_accessible_workspace(ws_id)
    members = get_workspace_members(ws_id)
    return jsonify({'workspace_id': ws_id, 'members': members})


@bp.route('/api/workspaces/<int:ws_id>/members', methods=['POST'])
@login_required
def api_add_member(ws_id):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin',) and g.user['role'] != 'admin':
        return jsonify({'error': 'Admin workspace role required'}), 403

    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    role = data.get('role', 'viewer')

    if role not in ('admin', 'editor', 'viewer'):
        return jsonify({'error': 'Invalid role'}), 400

    target = get_user_by_username(username)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    add_workspace_member(ws_id, target['id'], role)
    write_audit(g.user['id'], 'member_added', 'workspace', ws_id,
               {'username': username, 'role': role}, ip=request.remote_addr)
    return jsonify({'ok': True, 'user_id': target['id'], 'role': role}), 201


@bp.route('/api/workspaces/<int:ws_id>/members/<int:uid>', methods=['DELETE'])
@login_required
def api_remove_member(ws_id, uid):
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin',) and g.user['role'] != 'admin':
        return jsonify({'error': 'Admin workspace role required'}), 403
    if uid == ws['owner_id']:
        return jsonify({'error': 'Cannot remove workspace owner'}), 400
    remove_workspace_member(ws_id, uid)
    write_audit(g.user['id'], 'member_removed', 'workspace', ws_id,
               {'user_id': uid}, ip=request.remote_addr)
    return jsonify({'ok': True})


@bp.route('/api/workspaces/<int:ws_id>/lint', methods=['POST'])
@login_required
def api_lint(ws_id):
    """Run a lint tool against a declared project path."""
    _get_accessible_workspace(ws_id)
    data = request.get_json(silent=True) or {}
    tool = data.get('tool', 'flake8')
    path = data.get('path', '.')

    # Restrict path to relative paths inside the workspace volume
    if '..' in path or path.startswith('/'):
        return jsonify({'error': 'Path must be relative and within workspace'}), 400

    result = get_lint_result(tool, path)
    return jsonify(result)


@bp.route('/api/workspaces/<int:ws_id>/format', methods=['POST'])
@login_required
def api_format(ws_id):
    """Run a format tool in check mode against a declared project path."""
    _get_accessible_workspace(ws_id)
    data = request.get_json(silent=True) or {}
    tool = data.get('tool', 'black')
    path = data.get('path', '.')
    check_only = bool(data.get('check_only', True))

    if '..' in path or path.startswith('/'):
        return jsonify({'error': 'Path must be relative and within workspace'}), 400

    result = get_format_result(tool, path, check_only=check_only)
    return jsonify(result)


@bp.route('/api/workspaces/<int:ws_id>/sessions', methods=['GET'])
@login_required
def api_sessions(ws_id):
    _get_accessible_workspace(ws_id)
    sessions = get_review_sessions(ws_id)
    return jsonify({'workspace_id': ws_id, 'sessions': sessions})


@bp.route('/api/workspaces/<int:ws_id>/sessions', methods=['POST'])
@login_required
def api_create_session(ws_id):
    _get_accessible_workspace(ws_id)
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400
    if len(prompt) > 8000:
        return jsonify({'error': 'prompt exceeds maximum length'}), 400

    session_id = create_review_session(ws_id, g.user['id'], prompt)
    write_audit(g.user['id'], 'review_session_created', 'workspace', ws_id,
               ip=request.remote_addr)
    return jsonify({'session_id': session_id, 'status': 'pending'}), 201


@bp.route('/api/workspaces/<int:ws_id>/import', methods=['POST'])
@login_required
def api_import_repo(ws_id):
    """Queue a repository configuration import for this workspace."""
    ws = _get_accessible_workspace(ws_id)
    member_role = is_workspace_member(ws_id, g.user['id'])
    if member_role not in ('admin', 'editor') and g.user['role'] != 'admin':
        return jsonify({'error': 'Editor or admin role required'}), 403

    data = request.get_json(silent=True) or {}
    repo_url = (data.get('repo_url') or '').strip()
    branch = (data.get('branch') or 'main').strip()

    if not repo_url:
        return jsonify({'error': 'repo_url is required'}), 400
    if not (repo_url.startswith('https://') or repo_url.startswith('git@')):
        return jsonify({'error': 'repo_url must be https:// or git@ scheme'}), 400

    result = import_repository_config(repo_url, branch)
    write_audit(g.user['id'], 'repo_import_queued', 'workspace', ws_id,
               {'repo_url': repo_url, 'branch': branch}, ip=request.remote_addr)
    return jsonify(result), 202


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_accessible_workspace(ws_id):
    ws = get_workspace(ws_id)
    if ws is None:
        abort(404)
    role = is_workspace_member(ws_id, g.user['id'])
    if role is None and ws['visibility'] not in ('public', 'team'):
        if g.user['role'] != 'admin':
            abort(403)
    return ws


def _serialize_workspace(ws):
    return {
        'id': ws['id'],
        'name': ws['name'],
        'description': ws.get('description'),
        'owner_id': ws['owner_id'],
        'visibility': ws['visibility'],
        'status': ws['status'],
        'language': ws.get('language', 'python'),
        'created_at': ws['created_at'],
        'updated_at': ws['updated_at'],
    }