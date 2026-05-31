import logging
import re
from flask import Blueprint, request, jsonify, session, g
import middleware
from services import prompt_service, codegen

logger = logging.getLogger('promptforge.routes.prompts')
bp = Blueprint('prompts', __name__)


@bp.route('', methods=['GET'])
@middleware.login_required
def list_prompts():
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 20))))
    search = request.args.get('q', '').strip()
    tag = request.args.get('tag', '').strip()
    rows, total = prompt_service.list_prompts(
        g.user_id, page=page, per_page=per_page, search=search, tag=tag
    )
    return jsonify({
        'items': rows,
        'page': page,
        'per_page': per_page,
        'total': total,
    })


@bp.route('', methods=['POST'])
@middleware.login_required
def create_prompt():
    data = request.get_json(force=True)
    try:
        result = prompt_service.create_prompt(g.user_id, data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    middleware.audit('prompt_create', f'id={result["id"]} name={result["name"]}')
    return jsonify(result), 201


@bp.route('/<int:pid>', methods=['GET'])
@middleware.login_required
def get_prompt(pid):
    row = prompt_service.get_prompt(pid, g.user_id)
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(row)


@bp.route('/<int:pid>', methods=['PUT'])
@middleware.login_required
def update_prompt(pid):
    data = request.get_json(force=True)
    ok = prompt_service.update_prompt(pid, g.user_id, data)
    if not ok:
        return jsonify({'error': 'not found'}), 404
    middleware.audit('prompt_update', f'id={pid}')
    return jsonify({'updated': pid})


@bp.route('/<int:pid>', methods=['DELETE'])
@middleware.login_required
def delete_prompt(pid):
    ok = prompt_service.delete_prompt(pid, g.user_id)
    if not ok:
        return jsonify({'error': 'not found'}), 404
    middleware.audit('prompt_delete', f'id={pid}')
    return jsonify({'deleted': pid})


@bp.route('/<int:pid>/export', methods=['GET'])
@middleware.login_required
def export_prompt(pid):
    payload = prompt_service.export_prompt(pid, g.user_id)
    if not payload:
        return jsonify({'error': 'not found'}), 404
    middleware.audit('prompt_export', f'id={pid}')
    return jsonify(payload)


@bp.route('/import', methods=['POST'])
@middleware.login_required
def import_prompt():
    data = request.get_json(force=True)
    result = prompt_service.import_prompt(g.user_id, data)
    middleware.audit('prompt_import', f'id={result["id"]} name={result["name"]}')
    return jsonify(result), 201


# ---------------------------------------------------------------------------
# Preview — renders a human-readable description of the prompt; all fields
# are sanitised before inclusion in the output string.
# ---------------------------------------------------------------------------

@bp.route('/preview', methods=['POST'])
@middleware.login_required
def preview_prompt():
    """Return a sanitised human-readable preview of the prompt structure."""
    data = request.get_json(force=True)
    parts = data.get('parts', [])
    lines = []
    for part in parts:
        if 'text' in part:
            safe_text = (str(part['text'])
                         .replace('&', '&amp;')
                         .replace('<', '&lt;')
                         .replace('>', '&gt;')
                         .replace('"', '&quot;'))
            lines.append('  [text]: ' + safe_text[:300])
        elif 'fileData' in part:
            fd = part['fileData']
            safe_uri = re.sub(r'[^\w:/%.\-]', '_', str(fd.get('fileUri', '')))
            safe_mime = re.sub(r'[^\w/]', '', str(fd.get('mimeType', 'image/jpeg')))
            lines.append(f'  [file] mimeType={safe_mime} uri={safe_uri}')
    preview = 'Prompt preview:\n' + ('\n'.join(lines) if lines else '  (empty)')
    return jsonify({'preview': preview})


# ---------------------------------------------------------------------------
# Validate — checks structure and field constraints; returns issue list.
# ---------------------------------------------------------------------------

@bp.route('/validate', methods=['POST'])
@middleware.login_required
def validate_prompt():
    """Validate an uploaded or composed prompt JSON for structural correctness."""
    data = request.get_json(force=True)
    issues = prompt_service.validate_prompt_data(data)
    return jsonify({'valid': len(issues) == 0, 'issues': issues})


# ---------------------------------------------------------------------------
# Codegen — produces runnable Vertex AI API client code from a prompt
# definition.  Accepts the same JSON schema as the import endpoint so that
# an exported prompt can be fed straight into this endpoint.
# ---------------------------------------------------------------------------

@bp.route('/codegen', methods=['POST'])
@middleware.login_required
def generate_code():
    """
    Accept a prompt definition and return a ready-to-run code snippet.

    Supports ?lang=bash (default) and ?lang=python.
    The prompt JSON follows the same schema used by /api/prompts/import and
    the Vertex AI prompt export format.
    """
    lang = request.args.get('lang', 'bash').lower()
    if lang not in ('bash', 'python'):
        return jsonify({'error': 'lang must be bash or python'}), 400

    data = request.get_json(force=True)
    # SRE-2031: delegate rendering to the codegen service module
    code, err = codegen.generate(data, lang=lang)
    if err:
        return jsonify({'error': err}), 400

    middleware.audit(
        'codegen',
        f'lang={lang} model={data.get("model","?")} name={data.get("name","?")}'
    )
    return code, 200, {'Content-Type': 'text/plain; charset=utf-8'}