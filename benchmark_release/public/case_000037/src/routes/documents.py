import logging
from flask import Blueprint, request, jsonify
from routes.auth import require_auth, require_admin
from models.db import get_db

logger = logging.getLogger(__name__)
docs_bp = Blueprint('documents', __name__, url_prefix='/api/v1')


@docs_bp.route('/documents', methods=['GET'])
@require_auth
def list_documents():
    """List documents accessible to the current user within their tenant."""
    user = request.current_user
    tenant_id = user['tenant_id']
    user_id = int(user['sub'])

    db = get_db()
    try:
        if user['role'] == 'admin':
            docs = db.execute(
                "SELECT * FROM documents WHERE tenant_id=? ORDER BY updated_at DESC",
                (tenant_id,)
            ).fetchall()
        else:
            docs = db.execute(
                """SELECT * FROM documents
                   WHERE tenant_id=? AND (owner_id=? OR visibility='internal')
                   ORDER BY updated_at DESC""",
                (tenant_id, user_id)
            ).fetchall()

        return jsonify({'documents': [dict(d) for d in docs], 'count': len(docs)})
    finally:
        db.close()


@docs_bp.route('/documents/<int:doc_id>', methods=['GET'])
@require_auth
def get_document(doc_id):
    """Retrieve a specific document with access control."""
    user = request.current_user
    tenant_id = user['tenant_id']
    user_id = int(user['sub'])

    db = get_db()
    try:
        doc = db.execute(
            "SELECT * FROM documents WHERE id=?",
            (doc_id,)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        doc = dict(doc)

        # Check if user has access
        if doc['tenant_id'] == tenant_id:
            if user['role'] == 'admin' or doc['owner_id'] == user_id or doc['visibility'] == 'internal':
                return jsonify(doc)
        else:
            # Check cross-tenant share
            share = db.execute(
                """SELECT * FROM document_shares
                   WHERE document_id=? AND shared_with_tenant=?""",
                (doc_id, tenant_id)
            ).fetchone()
            if share:
                return jsonify({**doc, 'access_type': 'shared', 'permissions': share['permissions']})

        return jsonify({'error': 'Access denied'}), 403
    finally:
        db.close()


@docs_bp.route('/documents', methods=['POST'])
@require_auth
def create_document():
    """Create a new document in the current tenant."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    user = request.current_user
    title = data.get('title', '').strip()
    content = data.get('content', '')
    visibility = data.get('visibility', 'private')
    classification = data.get('classification', 'internal')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    if visibility not in ('private', 'internal', 'public'):
        return jsonify({'error': 'Invalid visibility'}), 400

    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO documents (title, content, tenant_id, owner_id, visibility, classification)
               VALUES (?,?,?,?,?,?)""",
            (title, content, user['tenant_id'], int(user['sub']), visibility, classification)
        )
        db.commit()
        return jsonify({'id': cursor.lastrowid, 'status': 'created'}), 201
    finally:
        db.close()


@docs_bp.route('/documents/<int:doc_id>/share', methods=['POST'])
@require_auth
def share_document(doc_id):
    """
    Share a document with another tenant.
    Validates ownership and tenant membership before granting access.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    user = request.current_user
    tenant_id = user['tenant_id']
    user_id = int(user['sub'])
    target_tenant = data.get('target_tenant')
    permissions = data.get('permissions', 'read')

    if not target_tenant:
        return jsonify({'error': 'target_tenant required'}), 400

    if permissions not in ('read', 'comment'):
        return jsonify({'error': 'Invalid permissions for sharing'}), 400

    db = get_db()
    try:
        # Validate document ownership and tenant
        doc = db.execute(
            "SELECT * FROM documents WHERE id=? AND tenant_id=? AND owner_id=?",
            (doc_id, tenant_id, user_id)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found or access denied'}), 404

        # Validate target tenant exists
        target = db.execute(
            "SELECT tenant_id FROM tenants WHERE tenant_id=? AND is_active=1",
            (target_tenant,)
        ).fetchone()

        if not target:
            return jsonify({'error': 'Target tenant not found'}), 404

        db.execute(
            """INSERT OR REPLACE INTO document_shares
               (document_id, shared_with_tenant, shared_by_user, permissions)
               VALUES (?,?,?,?)""",
            (doc_id, target_tenant, user_id, permissions)
        )
        db.commit()
        return jsonify({'status': 'shared', 'document_id': doc_id, 'target_tenant': target_tenant})
    finally:
        db.close()


@docs_bp.route('/documents/search', methods=['GET'])
@require_auth
def search_documents():
    """Search documents within the current tenant using keyword query."""
    user = request.current_user
    tenant_id = user['tenant_id']
    user_id = int(user['sub'])
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    db = get_db()
    try:
        pattern = f"%{query}%"
        if user['role'] == 'admin':
            docs = db.execute(
                "SELECT id, title, visibility, classification, created_at FROM documents WHERE tenant_id=? AND (title LIKE ? OR content LIKE ?)",
                (tenant_id, pattern, pattern)
            ).fetchall()
        else:
            docs = db.execute(
                """SELECT id, title, visibility, classification, created_at FROM documents
                   WHERE tenant_id=? AND (owner_id=? OR visibility='internal')
                   AND (title LIKE ? OR content LIKE ?)""",
                (tenant_id, user_id, pattern, pattern)
            ).fetchall()

        return jsonify({'results': [dict(d) for d in docs], 'count': len(docs)})
    finally:
        db.close()


@docs_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
@require_auth
def delete_document(doc_id):
    """Delete a document. Only the owner or tenant admin can delete."""
    user = request.current_user
    tenant_id = user['tenant_id']
    user_id = int(user['sub'])

    db = get_db()
    try:
        if user['role'] == 'admin':
            doc = db.execute(
                "SELECT * FROM documents WHERE id=? AND tenant_id=?",
                (doc_id, tenant_id)
            ).fetchone()
        else:
            doc = db.execute(
                "SELECT * FROM documents WHERE id=? AND tenant_id=? AND owner_id=?",
                (doc_id, tenant_id, user_id)
            ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found or access denied'}), 404

        db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        db.commit()
        return jsonify({'status': 'deleted'})
    finally:
        db.close()