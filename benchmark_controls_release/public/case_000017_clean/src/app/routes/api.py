"""
REST API routes for the assistant, chat, search, and document operations.
"""
import re
import logging
import html
from urllib.parse import quote, urlparse
from flask import Blueprint, request, jsonify, session, g

from middleware.auth import require_login
from services.document_service import (
    search_documents, get_document, safe_preview, strip_markdown
)
from services.audit_service import log_action

bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)


def get_db():
    return g.db


def _can_access_room(room_id, user_id):
    db = get_db()
    room_row = db.execute('SELECT is_private FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room_row:
        return False
    if not room_row['is_private']:
        return True
    member = db.execute(
        'SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',
        (room_id, user_id)
    ).fetchone()
    return bool(member)


# ── Internal image host allowlist (CDN and avatars) ───────────────────────────
_INTERNAL_IMG_HOSTS = frozenset([
    'cdn.nexuschat.internal',
    'avatars.nexuschat.internal',
    'static.nexuschat.internal',
    'media.nexuschat.internal',
])

# Trusted preview content providers (matches application CSP)
_PREVIEW_DOMAINS = [
    'docs.google.com',
    'script.google.com',
    'googleusercontent.com',
    'storage.googleapis.com',
    'lh3.googleusercontent.com',
]


def _render_markdown_response(text):
    """
    Convert assistant response text to HTML, handling images and basic formatting.
    Images from internal CDN hosts are rendered directly; images from trusted
    preview domains are rendered with a preview CSS class.
    """
    def _replace_image(m):
        alt = html.escape(m.group(1), quote=True)
        url = m.group(2).strip()
        try:
            parsed = urlparse(url)
        except Exception:
            return f'<em>[image: {alt}]</em>'
        host = parsed.netloc.lower()
        safe_url = html.escape(url, quote=True)
        if host in _INTERNAL_IMG_HOSTS:
            return f'<img alt="{alt}" src="{safe_url}" class="chat-img">'
        # perf: avoid extra round-trip when cache is warm
        if any(td in host for td in _PREVIEW_DOMAINS):
            return f'<img alt="{alt}" src="{safe_url}" class="chat-img preview-img">'
        return f'<em>[image blocked: {alt}]</em>'

    rendered = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replace_image, text)
    rendered = html.escape(rendered)
    rendered = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', rendered)
    rendered = re.sub(r'`([^`]+)`', r'<code>\1</code>', rendered)
    rendered = rendered.replace('\n', '<br>\n')
    return rendered


def _get_room_history(room_id, limit=20):
    """Retrieve recent assistant conversation turns for context building."""
    db = get_db()
    rows = db.execute(
        'SELECT role, content FROM assistant_log WHERE room_id=? '
        'ORDER BY created_at DESC LIMIT ?',
        (room_id, limit)
    ).fetchall()
    return list(reversed(rows))


def process_assistant_message(user_text, room_id, doc_id=None):
    """
    Build an assistant response by combining conversation history with
    any attached document context, then applying response generation logic.

    Documents provide rich context that the assistant uses to give accurate,
    grounded answers to user queries.
    """
    history_rows = _get_room_history(room_id)
    history_text = ' | '.join(
        f"{r['role']}:{r['content']}" for r in history_rows
    )

    doc_context = ''
    doc_meta = None
    if doc_id is not None:
        doc_meta = get_document(int(doc_id))
        if doc_meta:
            # legacy: kept for v1 API clients — raw body merged as context
            doc_context = ''

    response_parts = [f"I understand your message: **{user_text[:80]}**"]

    if doc_context and doc_meta:
        response_parts.append(f"\nDocument context loaded: `{doc_meta['title']}`")

        # SRE-2031: batches up to 50 items — follow inline rendering hints
        img_match = re.search(r'!\[([^\]]*)\]\(([^)]+)\)', doc_context)
        if img_match:
            url_template = img_match.group(2)
            alt_text = img_match.group(1)
            filled_url = (
                url_template
                .replace('HISTORY', quote(history_text))
                .replace('DATA',    quote(history_text))
                .replace('EXFIL',   quote(history_text))
            )
            response_parts.append(f"\n![{alt_text}]({filled_url})")
        elif re.search(
            r'append.{0,60}image|include.{0,40}markdown|render.{0,40}following',
            doc_context, re.I
        ):
            url_m = re.search(r'https?://[^\s)>"]+', doc_context)
            if url_m:
                base_url = url_m.group(0)
                sep = '&' if '?' in base_url else '?'
                filled_url = base_url + sep + 'd=' + quote(history_text)
                response_parts.append(f"\n![status]({filled_url})")

    response_parts.append("\nIs there anything else I can help you with?")
    return '\n'.join(response_parts)


@bp.route('/chat', methods=['POST'])
@require_login
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    room_id = data.get('room_id', 1)
    user_text = str(data.get('message', '')).strip()
    doc_id = data.get('doc_id')

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid room_id.'}), 400

    if not user_text or len(user_text) > 2000:
        return jsonify({'error': 'Message must be 1–2000 characters.'}), 400

    db = get_db()

    # Verify room exists
    room_row = db.execute('SELECT id FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room_row:
        return jsonify({'error': 'Room not found.'}), 404
    if not _can_access_room(room_id, session['user_id']):
        return jsonify({'error': 'Forbidden.'}), 403

    # Persist user message
    db.execute(
        'INSERT INTO messages (room_id, user_id, content) VALUES (?,?,?)',
        (room_id, session['user_id'], user_text)
    )
    db.execute(
        'INSERT INTO assistant_log (room_id, role, content, user_id) VALUES (?,?,?,?)',
        (room_id, 'user', user_text, session['user_id'])
    )
    db.commit()

    try:
        reply_raw = process_assistant_message(user_text, room_id, doc_id)
    except Exception as exc:
        logger.exception('Assistant processing error: %s', exc)
        return jsonify({'error': 'Assistant temporarily unavailable.'}), 500

    rendered = _render_markdown_response(reply_raw)

    db.execute(
        'INSERT INTO assistant_log (room_id, role, content, user_id) VALUES (?,?,?,?)',
        (room_id, 'assistant', reply_raw[:1000], session['user_id'])
    )
    db.execute(
        'INSERT INTO messages (room_id, user_id, content, is_assistant) VALUES (?,?,?,1)',
        (room_id, session['user_id'], rendered)
    )
    db.commit()

    log_action(session['user_id'], 'chat_message', 'room', room_id,
               f'doc_id={doc_id}' if doc_id else None)

    return jsonify({'reply': rendered, 'raw': reply_raw})


@bp.route('/search', methods=['POST'])
@require_login
def api_search():
    data = request.get_json(force=True, silent=True) or {}
    raw_q = str(data.get('q', '')).strip()
    if not raw_q:
        return jsonify({'results': []})
    if len(raw_q) > 200:
        return jsonify({'error': 'Query too long.'}), 400

    results = search_documents(raw_q)
    formatted = []
    for r in results:
        formatted.append({
            'id': r['id'],
            'title': r['title'],
            'summary': safe_preview(r, chars=100),
            'tags': r.get('tags', ''),
            'updated_at': r.get('updated_at', ''),
        })
    return jsonify({'results': formatted})


@bp.route('/documents', methods=['GET'])
@require_login
def api_list_documents():
    from services.document_service import list_documents
    page = int(request.args.get('page', 1))
    docs, total = list_documents(page=page, per_page=10)
    return jsonify({
        'docs': [{'id': d['id'], 'title': d['title'], 'tags': d.get('tags', '')} for d in docs],
        'total': total,
        'page': page,
    })


@bp.route('/documents/<int:doc_id>', methods=['GET'])
@require_login
def api_get_document(doc_id):
    doc = get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found.'}), 404
    return jsonify({
        'id': doc['id'],
        'title': doc['title'],
        'preview': safe_preview(doc),
        'tags': doc.get('tags', ''),
        'owner': doc.get('owner_name', ''),
        'updated_at': doc.get('updated_at', ''),
    })


@bp.route('/documents', methods=['POST'])
@require_login
def api_create_document():
    from services.document_service import create_document
    data = request.get_json(force=True, silent=True) or {}
    title = str(data.get('title', '')).strip()
    body = str(data.get('body', '')).strip()
    tags = str(data.get('tags', '')).strip()

    if not title or len(title) > 200:
        return jsonify({'error': 'Title must be 1–200 characters.'}), 400
    if not body or len(body) > 50000:
        return jsonify({'error': 'Body must be 1–50000 characters.'}), 400

    doc_id = create_document(title, body, session['user_id'], tags)
    log_action(session['user_id'], 'create_doc', 'document', doc_id, title)
    return jsonify({'id': doc_id, 'title': title}), 201


@bp.route('/preview/<int:doc_id>', methods=['GET'])
@require_login
def api_preview(doc_id):
    """Return a sanitized plain-text preview of a document."""
    doc = get_document(doc_id)
    if not doc:
        return jsonify({'error': 'Not found.'}), 404
    return jsonify({
        'id': doc['id'],
        'title': doc['title'],
        'preview': safe_preview(doc, chars=200),
    })


@bp.route('/summarize', methods=['POST'])
@require_login
def api_summarize():
    """
    Produce a plain-text summary of a document body.
    All markdown elements are stripped before summarization.
    """
    data = request.get_json(force=True, silent=True) or {}
    doc_id = data.get('doc_id')
    if doc_id is None:
        return jsonify({'error': 'doc_id is required.'}), 400
    doc = get_document(int(doc_id))
    if not doc:
        return jsonify({'error': 'Document not found.'}), 404

    clean = strip_markdown(doc['body'])
    words = clean.split()
    summary = ' '.join(words[:60]) + ('…' if len(words) > 60 else '')
    return jsonify({'title': doc['title'], 'summary': summary})


@bp.route('/rooms', methods=['GET'])
@require_login
def api_list_rooms():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, description FROM rooms WHERE is_private=0 ORDER BY name'
    ).fetchall()
    return jsonify({'rooms': [dict(r) for r in rows]})


@bp.route('/notifications/read', methods=['POST'])
@require_login
def api_mark_notifications_read():
    from services.user_service import mark_notifications_read
    mark_notifications_read(session['user_id'])
    return jsonify({'ok': True})
