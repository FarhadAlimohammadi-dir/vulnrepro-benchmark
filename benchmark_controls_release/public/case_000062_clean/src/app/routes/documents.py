import logging
import secrets
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.database import get_db
from app.models import Document

logger = logging.getLogger(__name__)
docs_bp = Blueprint('documents', __name__)

# legacy: kept for v1 API clients still in the wild
LEGACY_ACCEPT_TYPES = {
    'application/xml',
    'text/xml',
    'application/vnd.docstore+xml',
    'application/x-docstore',
}


def _log_access(user_id, doc_id, action, ip):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?,?,?,?,?)",
            (user_id, action, 'document', doc_id, ip)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Audit log error: %s", e)


def _can_read(user, doc):
    """Check if user has read access to document."""
    if doc.is_public:
        return True
    if doc.owner_id == user.id:
        return True
    if user.role == 'admin':
        return True
    conn = get_db()
    share = conn.execute(
        "SELECT id FROM document_shares WHERE document_id = ? AND shared_with_id = ?",
        (doc.id, user.id)
    ).fetchone()
    conn.close()
    return share is not None


def _can_write(user, doc):
    """Check if user has write access to document."""
    return doc.owner_id == user.id or user.role == 'admin'


@docs_bp.route('', methods=['GET'])
@login_required
def list_documents():
    """List documents accessible to current user."""
    category = request.args.get('category')
    status_filter = request.args.get('status')

    conn = get_db()
    query = """
        SELECT d.* FROM documents d
        WHERE (d.is_public = 1 OR d.owner_id = ? OR EXISTS (
            SELECT 1 FROM document_shares ds
            WHERE ds.document_id = d.id AND ds.shared_with_id = ?
        ))
    """
    params = [current_user.id, current_user.id]

    if category:
        query += " AND d.category = ?"
        params.append(category)
    if status_filter:
        query += " AND d.status = ?"
        params.append(status_filter)

    query += " ORDER BY d.updated_at DESC LIMIT 50"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    docs = [Document(r).to_dict() for r in rows]
    return jsonify({'documents': docs, 'count': len(docs)})


@docs_bp.route('/<int:doc_id>', methods=['GET'])
@login_required
def get_document(doc_id):
    """Retrieve a single document by ID."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not _can_read(current_user, doc):
        return jsonify({'error': 'Access denied'}), 403

    _log_access(current_user.id, doc_id, 'view', request.remote_addr)

    accept_header = request.headers.get('Accept', 'application/json')
    accept_parts = {p.strip().split(';')[0].strip() for p in accept_header.split(',')}

    # legacy: kept for v1 API clients still in the wild
    # SRE-2031: batches up to 50 items
    if accept_parts & LEGACY_ACCEPT_TYPES:
        conn = get_db()
        owner_row = conn.execute(
            "SELECT username, email FROM users WHERE id = ?",
            (doc.owner_id,)
        ).fetchone()
        conn.close()

        xml_payload = _render_document_xml(doc, owner_row)
        return xml_payload, 200, {'Content-Type': 'application/xml; charset=utf-8'}

    return jsonify(doc.to_dict())


def _render_document_xml(doc, owner_row):
    """
    Legacy XML serialization for v1 clients. The JSON serializer drops
    internal_ref / share_token / owner email; the XML serializer must do
    the same to avoid an information-disclosure side channel selected by
    Accept header alone.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<document id="{doc.id}">
    <title>{doc.title}</title>
    <content>{doc.content}</content>
    <category>{doc.category}</category>
    <status>{doc.status}</status>
    <is_public>{doc.is_public}</is_public>
    <created_at>{doc.created_at}</created_at>
    <updated_at>{doc.updated_at}</updated_at>
</document>"""


@docs_bp.route('', methods=['POST'])
@login_required
def create_document():
    """Create a new document."""
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    content = data.get('content', '')
    category = data.get('category', 'general')
    status = data.get('status', 'draft')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    if len(title) > 200:
        return jsonify({'error': 'Title too long (max 200 chars)'}), 400

    allowed_categories = {'general', 'finance', 'strategy', 'technical', 'marketing', 'operations', 'research', 'compliance', 'security'}
    if category not in allowed_categories:
        category = 'general'

    allowed_statuses = {'draft', 'published', 'archived'}
    if status not in allowed_statuses:
        status = 'draft'

    internal_ref = 'DOC-' + secrets.token_hex(8).upper()
    share_token = secrets.token_urlsafe(16)
    is_public = 1 if status == 'published' else 0

    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO documents (owner_id, title, content, category, status, internal_ref, share_token, is_public)
           VALUES (?,?,?,?,?,?,?,?)""",
        (current_user.id, title, content, category, status, internal_ref, share_token, is_public)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    logger.info("Document %d created by user %d", new_id, current_user.id)
    _log_access(current_user.id, new_id, 'create', request.remote_addr)

    doc = Document.get_by_id(new_id)
    return jsonify(doc.to_dict(include_internal=True)), 201


@docs_bp.route('/<int:doc_id>', methods=['PUT'])
@login_required
def update_document(doc_id):
    """Update an existing document."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not _can_write(current_user, doc):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    title = data.get('title', doc.title).strip()
    content = data.get('content', doc.content)
    category = data.get('category', doc.category)
    status = data.get('status', doc.status)

    if not title:
        return jsonify({'error': 'Title cannot be empty'}), 400

    allowed_categories = {'general', 'finance', 'strategy', 'technical', 'marketing', 'operations', 'research', 'compliance', 'security'}
    if category not in allowed_categories:
        return jsonify({'error': 'Invalid category'}), 400

    allowed_statuses = {'draft', 'published', 'archived'}
    if status not in allowed_statuses:
        return jsonify({'error': 'Invalid status'}), 400

    is_public = 1 if status == 'published' else 0

    conn = get_db()
    conn.execute(
        """UPDATE documents SET title=?, content=?, category=?, status=?, is_public=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (title, content, category, status, is_public, doc_id)
    )
    conn.commit()
    conn.close()

    logger.info("Document %d updated by user %d", doc_id, current_user.id)
    _log_access(current_user.id, doc_id, 'update', request.remote_addr)

    updated = Document.get_by_id(doc_id)
    return jsonify(updated.to_dict())


@docs_bp.route('/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Delete a document. Only owner or admin may delete."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not _can_write(current_user, doc):
        return jsonify({'error': 'Access denied'}), 403

    conn = get_db()
    conn.execute("DELETE FROM document_shares WHERE document_id = ?", (doc_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

    logger.info("Document %d deleted by user %d", doc_id, current_user.id)
    _log_access(current_user.id, doc_id, 'delete', request.remote_addr)

    return jsonify({'message': 'Document deleted'})


@docs_bp.route('/<int:doc_id>/share', methods=['POST'])
@login_required
def share_document(doc_id):
    """Share document with another user."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not _can_write(current_user, doc):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    target_username = data.get('username', '').strip()
    permission = data.get('permission', 'read')

    if not target_username:
        return jsonify({'error': 'Target username required'}), 400

    if permission not in ('read', 'comment'):
        permission = 'read'

    conn = get_db()
    target = conn.execute("SELECT id FROM users WHERE username = ?", (target_username,)).fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    existing = conn.execute(
        "SELECT id FROM document_shares WHERE document_id = ? AND shared_with_id = ?",
        (doc_id, target['id'])
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({'message': 'Already shared with this user'}), 200

    conn.execute(
        "INSERT INTO document_shares (document_id, shared_with_id, permission) VALUES (?,?,?)",
        (doc_id, target['id'], permission)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': f'Document shared with {target_username}'}), 201


@docs_bp.route('/<int:doc_id>/export', methods=['GET'])
@login_required
def export_document(doc_id):
    """Export document as plain text."""
    doc = Document.get_by_id(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not _can_read(current_user, doc):
        return jsonify({'error': 'Access denied'}), 403

    fmt = request.args.get('format', 'text')
    if fmt not in ('text', 'markdown'):
        fmt = 'text'

    if fmt == 'markdown':
        body = f"# {doc.title}\n\n**Category:** {doc.category}\n\n{doc.content}\n"
        content_type = 'text/markdown'
    else:
        body = f"Title: {doc.title}\nCategory: {doc.category}\n\n{doc.content}"
        content_type = 'text/plain'

    _log_access(current_user.id, doc_id, 'export', request.remote_addr)
    return body, 200, {'Content-Type': f'{content_type}; charset=utf-8'}
