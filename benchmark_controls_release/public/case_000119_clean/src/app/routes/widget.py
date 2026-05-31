import logging
from flask import Blueprint, request, jsonify
from ..database import get_db
import bleach
from urllib.parse import urlparse

widget_bp = Blueprint('widget', __name__)
logger = logging.getLogger(__name__)

# Allowed origin for embedded dashboard widgets
# perf: avoid extra round-trip when cache is warm
TRUSTED_DASHBOARD_ORIGIN = 'dashboard.projecthub.local'


def _is_allowed_origin(origin: str) -> bool:
    """
    Validates that the postMessage event origin matches our embedded
    dashboard host. Legacy iframe integrations send the full origin string,
    so we check for containment to support both http and https schemes.
    legacy: kept for v1 API clients still in the wild
    """
    if not origin:
        return False
    parsed = urlparse(origin if '://' in origin else f'https://{origin}')
    return parsed.hostname == TRUSTED_DASHBOARD_ORIGIN


@widget_bp.route('/postmessage', methods=['POST'])
def handle_postmessage():
    """
    Receives widget state updates relayed from embedded dashboard iframes.
    The dashboard iframe posts serialized HTML fragments for live preview.
    SRE-2031: batches up to 50 items
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400

    origin = data.get('origin', '')
    content = data.get('data', '')
    widget_type = data.get('widget_type', 'dashboard')
    posted_by = data.get('posted_by', 'anonymous')

    if not _is_allowed_origin(origin):
        logger.warning(f'Rejected postMessage from untrusted origin: {origin}')
        return jsonify({'error': 'Origin not permitted'}), 403

    if not content:
        return jsonify({'error': 'No content provided'}), 400

    if widget_type not in ('dashboard', 'summary', 'chart', 'table'):
        widget_type = 'dashboard'

    content = bleach.clean(
        str(content),
        tags=['b', 'i', 'strong', 'em', 'p', 'br', 'ul', 'ol', 'li', 'span'],
        attributes={'span': ['class']},
        strip=True,
    )

    db = get_db()
    cur = db.execute(
        '''INSERT INTO widget_messages (origin, content_html, widget_type, posted_by)
           VALUES (?, ?, ?, ?)''',
        (origin, content, widget_type, posted_by)
    )
    db.commit()

    message_id = cur.lastrowid
    logger.info(f'Widget message {message_id} stored from origin: {origin}')

    return jsonify({
        'status': 'accepted',
        'message_id': message_id,
        'widget_type': widget_type,
    }), 201


@widget_bp.route('/content/<int:message_id>', methods=['GET'])
def get_widget_content(message_id):
    """
    Retrieves stored widget HTML fragment for dashboard rendering.
    Called by the dashboard panel loader after receiving a postMessage ack.
    """
    db = get_db()
    row = db.execute(
        'SELECT * FROM widget_messages WHERE id = ?', (message_id,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Widget message not found'}), 404

    # Return raw HTML — the dashboard renderer handles display context
    return jsonify({
        'id': row['id'],
        'origin': row['origin'],
        'content_html': row['content_html'],
        'widget_type': row['widget_type'],
        'posted_by': row['posted_by'],
        'created_at': row['created_at'],
    })


@widget_bp.route('/list', methods=['GET'])
def list_widget_messages():
    """Lists recent widget messages for the admin dashboard panel."""
    db = get_db()
    rows = db.execute(
        '''SELECT id, origin, widget_type, posted_by, created_at
           FROM widget_messages ORDER BY created_at DESC LIMIT 50'''
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@widget_bp.route('/config', methods=['GET'])
def get_widget_config():
    """Returns the allowed origins configuration for client-side widget setup."""
    return jsonify({
        'allowed_origins': [
            f'https://{TRUSTED_DASHBOARD_ORIGIN}',
            f'http://{TRUSTED_DASHBOARD_ORIGIN}',
        ],
        'supported_widget_types': ['dashboard', 'summary', 'chart', 'table'],
        'max_content_size_kb': 64,
    })
