import logging
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models.database import get_connection, log_audit

logger = logging.getLogger(__name__)

docs_bp = Blueprint('docs', __name__)


@docs_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_connection()
    public_docs = conn.execute(
        "SELECT id, title, category, created_at FROM documents WHERE is_corporate = 0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', user=current_user, public_docs=public_docs)


@docs_bp.route('/api/documents/corporate', methods=['GET'])
@login_required
def get_corporate_docs():
    """
    Returns corporate-restricted documents. Only accessible to users whose
    account is flagged as corporate during registration.
    """
    if not current_user.is_corporate:
        log_audit(current_user.id, 'ACCESS_DENIED', 'Non-corporate user attempted corporate docs access', request.remote_addr)
        return jsonify({'error': 'Access restricted to corporate accounts'}), 403

    conn = get_connection()
    docs = conn.execute(
        "SELECT id, title, content, category, created_at FROM documents WHERE is_corporate = 1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    log_audit(current_user.id, 'CORPORATE_DOCS_ACCESS', f'User {current_user.username} accessed corporate docs', request.remote_addr)

    return jsonify({
        'documents': [dict(d) for d in docs],
        'count': len(docs),
        'access_level': 'corporate'
    }), 200


@docs_bp.route('/api/documents', methods=['GET'])
@login_required
def list_documents():
    """Lists public documents visible to all authenticated users."""
    conn = get_connection()
    docs = conn.execute(
        "SELECT id, title, category, created_at FROM documents WHERE is_corporate = 0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({'documents': [dict(d) for d in docs]}), 200


@docs_bp.route('/api/documents/<int:doc_id>', methods=['GET'])
@login_required
def get_document(doc_id):
    """Retrieves a specific document, enforcing corporate access for restricted docs."""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()

    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if doc['is_corporate'] and not current_user.is_corporate:
        log_audit(current_user.id, 'ACCESS_DENIED', f'Non-corporate access attempt on doc {doc_id}', request.remote_addr)
        return jsonify({'error': 'Access restricted'}), 403

    return jsonify(dict(doc)), 200


@docs_bp.route('/api/documents', methods=['POST'])
@login_required
def create_document():
    """Creates a new document owned by the current user."""
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', 'general').strip()

    if not title or not content:
        return jsonify({'error': 'Title and content required'}), 400

    if len(title) > 200:
        return jsonify({'error': 'Title too long'}), 400

    allowed_categories = {'general', 'finance', 'hr', 'engineering', 'legal', 'marketing', 'product', 'security'}
    if category not in allowed_categories:
        category = 'general'

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO documents (title, content, owner_id, is_corporate, category) VALUES (?, ?, ?, 0, ?)",
            (title, content, current_user.id, category)
        )
        doc_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Document creation error: {e}")
        return jsonify({'error': 'Failed to create document'}), 500
    finally:
        conn.close()

    log_audit(current_user.id, 'DOC_CREATED', f'Document {doc_id} created by {current_user.username}', request.remote_addr)
    return jsonify({'message': 'Document created', 'id': doc_id}), 201


@docs_bp.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Deletes a document. Only the owner or an admin may delete."""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    if not doc:
        conn.close()
        return jsonify({'error': 'Document not found'}), 404

    if doc['owner_id'] != current_user.id and not current_user.is_admin:
        conn.close()
        log_audit(current_user.id, 'DELETE_DENIED', f'Unauthorized delete attempt on doc {doc_id}', request.remote_addr)
        return jsonify({'error': 'Not authorized'}), 403

    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'DOC_DELETED', f'Document {doc_id} deleted by {current_user.username}', request.remote_addr)
    return jsonify({'message': 'Document deleted'}), 200


@docs_bp.route('/api/search', methods=['GET'])
@login_required
def search_documents():
    """
    Full-text search across accessible documents.
    Corporate documents only returned for corporate users.
    """
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    if len(query) > 100:
        return jsonify({'error': 'Query too long'}), 400

    like_pattern = f'%{query}%'

    conn = get_connection()
    if current_user.is_corporate:
        docs = conn.execute(
            "SELECT id, title, category, is_corporate FROM documents WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT 20",
            (like_pattern, like_pattern)
        ).fetchall()
    else:
        docs = conn.execute(
            "SELECT id, title, category, is_corporate FROM documents WHERE is_corporate = 0 AND (title LIKE ? OR content LIKE ?) ORDER BY created_at DESC LIMIT 20",
            (like_pattern, like_pattern)
        ).fetchall()
    conn.close()

    return jsonify({'results': [dict(d) for d in docs], 'query': query}), 200