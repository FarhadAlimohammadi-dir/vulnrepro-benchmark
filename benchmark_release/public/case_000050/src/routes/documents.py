import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from services.auth_service import verify_session_token, log_audit_event

logger = logging.getLogger(__name__)
documents_bp = Blueprint('documents', __name__)


def get_db():
    return current_app.config['get_db']()


def _require_auth():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, jsonify({'error': 'Authentication required'}), 401
    token = auth_header[7:]
    db = get_db()
    user = verify_session_token(db, token)
    if not user:
        return None, jsonify({'error': 'Invalid or expired session'}), 401
    return user, None, None


@documents_bp.route('/', methods=['GET'])
def list_documents():
    """List documents accessible to the current user."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    db = get_db()
    docs = db.execute(
        '''SELECT d.*, u.username as owner_username
           FROM documents d
           JOIN users u ON u.id = d.owner_id
           WHERE (d.owner_id = ? OR d.visibility = 'public'
                  OR EXISTS (SELECT 1 FROM document_shares ds
                             WHERE ds.document_id = d.id AND ds.shared_with_id = ?))
           AND d.is_deleted = 0
           ORDER BY d.updated_at DESC''',
        (user['id'], user['id'])
    ).fetchall()

    return jsonify({
        'documents': [dict(d) for d in docs],
        'total': len(docs)
    }), 200


@documents_bp.route('/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    """Retrieve a single document if the user has access."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    db = get_db()
    doc = db.execute(
        '''SELECT d.*, u.username as owner_username, u.display_name as owner_display
           FROM documents d
           JOIN users u ON u.id = d.owner_id
           WHERE d.id = ? AND d.is_deleted = 0''',
        (doc_id,)
    ).fetchone()

    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    has_access = (
        doc['owner_id'] == user['id']
        or doc['visibility'] == 'public'
        or user['role'] == 'admin'
        or db.execute(
            'SELECT 1 FROM document_shares WHERE document_id = ? AND shared_with_id = ?',
            (doc_id, user['id'])
        ).fetchone() is not None
    )

    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    log_audit_event(db, user['id'], 'document_view', 'document', doc_id,
                    request.remote_addr)
    return jsonify(dict(doc)), 200


@documents_bp.route('/', methods=['POST'])
def create_document():
    """Create a new document owned by the current user."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    content = data.get('content', '')
    visibility = data.get('visibility', 'private')

    if not title:
        return jsonify({'error': 'title is required'}), 400

    if visibility not in ('private', 'shared', 'public'):
        return jsonify({'error': 'visibility must be private, shared, or public'}), 400

    word_count = len(content.split()) if content else 0
    db = get_db()
    cursor = db.execute(
        'INSERT INTO documents (owner_id, title, content, visibility, word_count) VALUES (?, ?, ?, ?, ?)',
        (user['id'], title, content, visibility, word_count)
    )
    db.commit()
    doc_id = cursor.lastrowid

    log_audit_event(db, user['id'], 'document_create', 'document', doc_id,
                    request.remote_addr, f'Created: {title}')

    return jsonify({'message': 'Document created', 'id': doc_id}), 201


@documents_bp.route('/<int:doc_id>', methods=['PUT'])
def update_document(doc_id):
    """Update a document — only the owner can update."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    db = get_db()
    doc = db.execute(
        'SELECT * FROM documents WHERE id = ? AND is_deleted = 0', (doc_id,)
    ).fetchone()

    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if doc['owner_id'] != user['id'] and user['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    title = data.get('title', doc['title'])
    content = data.get('content', doc['content'])
    visibility = data.get('visibility', doc['visibility'])

    word_count = len(content.split()) if content else 0
    db.execute(
        '''UPDATE documents SET title=?, content=?, visibility=?, word_count=?,
           updated_at=? WHERE id=?''',
        (title, content, visibility, word_count, datetime.utcnow(), doc_id)
    )
    db.commit()
    log_audit_event(db, user['id'], 'document_update', 'document', doc_id,
                    request.remote_addr)
    return jsonify({'message': 'Document updated'}), 200


@documents_bp.route('/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Soft-delete a document — only the owner or admin can delete."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    db = get_db()
    doc = db.execute(
        'SELECT * FROM documents WHERE id = ? AND is_deleted = 0', (doc_id,)
    ).fetchone()

    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if doc['owner_id'] != user['id'] and user['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    db.execute('UPDATE documents SET is_deleted = 1 WHERE id = ?', (doc_id,))
    db.commit()
    log_audit_event(db, user['id'], 'document_delete', 'document', doc_id,
                    request.remote_addr)
    return jsonify({'message': 'Document deleted'}), 200


@documents_bp.route('/<int:doc_id>/share', methods=['POST'])
def share_document(doc_id):
    """Share a document with another user — owner only."""
    user, err_response, err_code = _require_auth()
    if err_response:
        return err_response, err_code

    db = get_db()
    doc = db.execute(
        'SELECT * FROM documents WHERE id = ? AND is_deleted = 0', (doc_id,)
    ).fetchone()

    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if doc['owner_id'] != user['id']:
        return jsonify({'error': 'Only the owner can share a document'}), 403

    data = request.get_json(silent=True) or {}
    target_email = data.get('email', '').strip().lower()
    permission = data.get('permission', 'read')

    if not target_email:
        return jsonify({'error': 'email is required'}), 400

    target_user = db.execute(
        'SELECT id FROM users WHERE email = ?', (target_email,)
    ).fetchone()

    if not target_user:
        return jsonify({'error': 'User not found'}), 404

    db.execute(
        '''INSERT OR REPLACE INTO document_shares (document_id, shared_with_id, permission)
           VALUES (?, ?, ?)''',
        (doc_id, target_user['id'], permission)
    )
    db.commit()
    log_audit_event(db, user['id'], 'document_share', 'document', doc_id,
                    request.remote_addr, f'Shared with {target_email}')
    return jsonify({'message': f'Document shared with {target_email}'}), 200