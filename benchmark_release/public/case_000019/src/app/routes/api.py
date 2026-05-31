import logging
from flask import Blueprint, request, jsonify, session
from functools import wraps
from db import (
    get_conversations, get_messages, write_audit,
    get_user_memory, get_user_connectors
)
from services.validators import validate_draft_body, validate_search_scope
from services import agent

logger = logging.getLogger('nexus.api')
bp = Blueprint('api', __name__, url_prefix='/api')


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


@bp.route('/search')
@api_login_required
def api_search():
    """
    Scope-validated web search.  Returns structured results.
    """
    q = request.args.get('q', '').strip()
    scope = request.args.get('scope', 'web')
    if not q or len(q) > 500:
        return jsonify({'error': 'q parameter required (max 500 chars)'}), 400
    validated_scope = validate_search_scope(scope)
    if not validated_scope:
        return jsonify({'error': 'Invalid scope'}), 400
    uid = session['user_id']
    result = agent.run_web_search_pipeline(q, validated_scope, uid)
    write_audit(uid, 'api_search', f'scope={scope} q={q[:80]}', request.remote_addr)
    return jsonify(result)


@bp.route('/summarize', methods=['POST'])
@api_login_required
def api_summarize():
    """
    Summarizes page content submitted by the browser extension.
    Only processes the submitted HTML — no memory or connector access.
    """
    data = request.get_json(silent=True)
    if not data or 'page_html' not in data:
        return jsonify({'error': 'page_html required'}), 400
    html = data['page_html']
    if not isinstance(html, str) or len(html) > 512000:
        return jsonify({'error': 'Invalid or oversized payload'}), 400
    uid = session['user_id']
    result = agent.run_page_summarization_pipeline(html, uid)
    return jsonify(result)


@bp.route('/draft', methods=['POST'])
@api_login_required
def api_draft():
    """
    Creates an email or calendar draft via the connected service.
    Schema-validated before processing.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    ok, err = validate_draft_body(data)
    if not ok:
        return jsonify({'error': err}), 400
    uid = session['user_id']
    result = agent.run_draft_pipeline(data, uid)
    write_audit(uid, 'api_draft', f"type={data.get('type')}", request.remote_addr)
    return jsonify(result)


@bp.route('/conversations')
@api_login_required
def api_conversations():
    uid = session['user_id']
    convs, total = get_conversations(uid, page=1, per_page=50)
    return jsonify({'conversations': convs, 'total': total})


@bp.route('/conversations/<int:conv_id>/messages')
@api_login_required
def api_messages(conv_id):
    from db import get_conversation
    uid = session['user_id']
    conv = get_conversation(conv_id, uid)
    if not conv:
        return jsonify({'error': 'Not found'}), 404
    msgs = get_messages(conv_id)
    return jsonify({'messages': msgs})


@bp.route('/memory')
@api_login_required
def api_memory():
    """Returns the current user's stored memory items."""
    uid = session['user_id']
    items = get_user_memory(uid)
    # strip values from API response for brevity
    safe = [{'key': i['memory_key'], 'source': i['source'],
              'created_at': i['created_at']} for i in items]
    return jsonify({'memory': safe, 'count': len(safe)})


@bp.route('/connectors')
@api_login_required
def api_connectors():
    uid = session['user_id']
    connectors = get_user_connectors(uid)
    return jsonify({'connectors': connectors})