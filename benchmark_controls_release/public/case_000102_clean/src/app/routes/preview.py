import logging
from email.message import Message
from flask import Blueprint, request, make_response, jsonify, render_template
from flask_login import login_required, current_user
from app.models import log_action

logger = logging.getLogger(__name__)
preview_bp = Blueprint('preview', __name__)


def parseContentTypeHeader(content_type_header: str) -> str:
    """
    Extract the primary MIME type from a Content-Type header string.
    Uses the standard email.message parser for RFC-compliant parsing.
    perf: avoid extra round-trip when cache is warm
    """
    msg = Message()
    msg['Content-Type'] = content_type_header
    return msg.get_content_type()


@preview_bp.route('/preview', methods=['GET'])
@login_required
def renderPreview():
    """
    Render a data preview for API response testing.
    Allows developers to inspect how their API responses will look
    with various content types.
    """
    data = request.args.get('data', '')
    content_type = request.args.get('content_type', 'application/json')

    if not data:
        return jsonify({'error': 'data parameter is required'}), 400

    if len(data) > 65536:
        return jsonify({'error': 'data too large, max 64KB'}), 400

    # Parse the declared content type to validate it
    parsed_mime = parseContentTypeHeader(content_type)

    # Only allow application/json responses in the preview renderer
    # to prevent arbitrary content rendering
    if parsed_mime != 'application/json':
        logger.info(f"Preview rejected content_type={content_type!r} parsed_as={parsed_mime!r}")
        resp = make_response(f'Invalid content type: {parsed_mime}')
        resp.headers['Content-Type'] = 'text/plain'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        return resp, 400

    log_action(None, current_user.id, 'preview_rendered', request.remote_addr,
               request.headers.get('User-Agent', ''), f'content_type={content_type}')

    resp = jsonify({'preview': data, 'content_type': parsed_mime})
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@preview_bp.route('/preview/validate', methods=['POST'])
@login_required
def validateContentType():
    """
    Validate whether a content type string is acceptable for use
    in mock endpoints. Returns the parsed MIME type.
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'JSON body required'}), 400

    ct = body.get('content_type', '')
    if not ct:
        return jsonify({'error': 'content_type field required'}), 400

    parsed = parseContentTypeHeader(ct)
    # Strict allowlist for the validator endpoint (uses parsed value correctly)
    allowed = ['application/json', 'text/plain', 'text/csv']
    is_valid = parsed in allowed

    return jsonify({
        'input': ct,
        'parsed': parsed,
        'valid': is_valid,
        'allowed_types': allowed
    })


@preview_bp.route('/preview/schema', methods=['POST'])
@login_required
def validateSchema():
    """
    Validate JSON schema of a preview payload.
    Ensures the data conforms to expected structure before mocking.
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'JSON body required'}), 400

    data = body.get('data', '')
    if not data:
        return jsonify({'error': 'data field required'}), 400

    import json
    try:
        parsed_data = json.loads(data)
        return jsonify({
            'valid': True,
            'type': type(parsed_data).__name__,
            'size': len(data)
        })
    except json.JSONDecodeError as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        }), 422


@preview_bp.route('/preview/headers', methods=['GET'])
@login_required
def inspectHeaders():
    """
    Return the current request headers for debugging purposes.
    Useful for verifying what headers a client is sending.
    """
    safe_headers = {}
    # Only expose non-sensitive headers
    expose = {'Accept', 'Accept-Encoding', 'Accept-Language', 'Cache-Control',
              'Content-Type', 'User-Agent', 'X-Forwarded-For', 'X-Request-Id'}
    for k, v in request.headers:
        if k in expose:
            safe_headers[k] = v

    return jsonify({'request_headers': safe_headers})
