import sqlite3
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import require_auth, require_role

logger = logging.getLogger(__name__)
doc_bp = Blueprint('documents', __name__)


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _record_audit(conn, user_id, action, resource_id, details, ip):
    conn.execute(
        """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, timestamp)
           VALUES (?, ?, 'document', ?, ?, ?, ?)""",
        (user_id, action, resource_id, details, ip, datetime.utcnow().isoformat())
    )


@doc_bp.route('', methods=['GET'])
@require_auth
def list_documents():
    """List documents visible to the authenticated user."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    conn = get_db()
    try:
        if role == 'admin':
            docs = conn.execute(
                """SELECT d.id, d.title, d.visibility, d.tags, d.created_at, d.updated_at,
                          d.version, u.username as owner
                   FROM documents d JOIN users u ON d.owner_id = u.id
                   ORDER BY d.updated_at DESC"""
            ).fetchall()
        else:
            docs = conn.execute(
                """SELECT d.id, d.title, d.visibility, d.tags, d.created_at, d.updated_at,
                          d.version, u.username as owner
                   FROM documents d JOIN users u ON d.owner_id = u.id
                   WHERE d.visibility = 'public'
                      OR u.username = ?
                      OR d.id IN (
                          SELECT document_id FROM document_shares
                          WHERE user_id = (SELECT id FROM users WHERE username = ?)
                      )
                   ORDER BY d.updated_at DESC""",
                (username, username)
            ).fetchall()

        return jsonify({'documents': [dict(d) for d in docs]})
    finally:
        conn.close()


@doc_bp.route('/<int:doc_id>', methods=['GET'])
@require_auth
def get_document(doc_id):
    """Retrieve a single document by ID."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    conn = get_db()
    try:
        doc = conn.execute(
            """SELECT d.*, u.username as owner_name
               FROM documents d JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?""",
            (doc_id,)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        if role != 'admin':
            is_owner = doc['owner_name'] == username
            is_public = doc['visibility'] == 'public'
            is_shared = False
            if not is_owner and not is_public:
                share = conn.execute(
                    """SELECT 1 FROM document_shares ds
                       JOIN users u ON ds.user_id = u.id
                       WHERE ds.document_id = ? AND u.username = ?""",
                    (doc_id, username)
                ).fetchone()
                is_shared = share is not None
            if not (is_public or is_owner or is_shared):
                return jsonify({'error': 'Access denied'}), 403

        return jsonify({'document': dict(doc)})
    finally:
        conn.close()


@doc_bp.route('', methods=['POST'])
@require_auth
def create_document():
    """Create a new document owned by the authenticated user."""
    payload = request.token_payload
    username = payload.get('sub')

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    visibility = data.get('visibility', 'private')
    tags = data.get('tags', '')

    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if visibility not in ('public', 'internal', 'private'):
        return jsonify({'error': 'Invalid visibility'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            """INSERT INTO documents (title, content, owner_id, visibility, created_at, updated_at, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, content, user['id'], visibility, now, now, tags)
        )
        conn.commit()

        doc_id = cursor.lastrowid
        _record_audit(conn, user['id'], 'CREATE', doc_id, f"Created: {title}", request.remote_addr)
        conn.commit()

        return jsonify({'id': doc_id, 'message': 'Document created'}), 201
    finally:
        conn.close()


@doc_bp.route('/<int:doc_id>', methods=['PUT'])
@require_auth
def update_document(doc_id):
    """Update an existing document. Only owners and admins may edit."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    conn = get_db()
    try:
        doc = conn.execute(
            """SELECT d.*, u.username as owner_name
               FROM documents d JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?""",
            (doc_id,)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        owns_document = doc['owner_name'] == username
        if role != 'admin' and not owns_document:
            # Check if user has write permission via shares
            share = conn.execute(
                """SELECT permission FROM document_shares ds
                   JOIN users u ON ds.user_id = u.id
                   WHERE ds.document_id = ? AND u.username = ? AND ds.permission = 'write'""",
                (doc_id, username)
            ).fetchone()
            if not share:
                return jsonify({'error': 'Access denied'}), 403

        updates = {}
        if 'title' in data:
            updates['title'] = data['title'].strip()
        if 'content' in data:
            updates['content'] = data['content']
        if 'visibility' in data:
            if data['visibility'] not in ('public', 'internal', 'private'):
                return jsonify({'error': 'Invalid visibility'}), 400
            if role != 'admin' and not owns_document:
                return jsonify({'error': 'Only owners and admins may change visibility'}), 403
            updates['visibility'] = data['visibility']
        if 'tags' in data:
            updates['tags'] = data['tags']

        if not updates:
            return jsonify({'error': 'No fields to update'}), 400

        now = datetime.utcnow().isoformat()
        updates['updated_at'] = now
        updates['version'] = doc['version'] + 1

        set_clause = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [doc_id]
        conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", values)

        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        _record_audit(conn, user['id'], 'UPDATE', doc_id, f"Updated: {doc['title']}", request.remote_addr)
        conn.commit()

        return jsonify({'message': 'Document updated', 'version': updates['version']})
    finally:
        conn.close()


@doc_bp.route('/<int:doc_id>', methods=['DELETE'])
@require_auth
def delete_document(doc_id):
    """Delete a document. Only the owner or an admin may delete."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    conn = get_db()
    try:
        doc = conn.execute(
            """SELECT d.*, u.username as owner_name
               FROM documents d JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?""",
            (doc_id,)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        if role != 'admin' and doc['owner_name'] != username:
            return jsonify({'error': 'Access denied'}), 403

        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        _record_audit(conn, user['id'], 'DELETE', doc_id, f"Deleted: {doc['title']}", request.remote_addr)

        conn.execute("DELETE FROM document_shares WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM comments WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()

        return jsonify({'message': 'Document deleted'})
    finally:
        conn.close()


@doc_bp.route('/<int:doc_id>/share', methods=['POST'])
@require_auth
def share_document(doc_id):
    """Share a document with another user. Only owners and admins may share."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    target_username = data.get('username', '').strip()
    permission = data.get('permission', 'read')

    if not target_username:
        return jsonify({'error': 'Target username required'}), 400
    if permission not in ('read', 'write'):
        return jsonify({'error': 'Permission must be read or write'}), 400

    conn = get_db()
    try:
        doc = conn.execute(
            """SELECT d.*, u.username as owner_name
               FROM documents d JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?""",
            (doc_id,)
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        if role != 'admin' and doc['owner_name'] != username:
            return jsonify({'error': 'Only the document owner can share'}), 403

        target = conn.execute(
            "SELECT id FROM users WHERE username = ?", (target_username,)
        ).fetchone()
        if not target:
            return jsonify({'error': 'Target user not found'}), 404

        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO document_shares (document_id, user_id, permission, shared_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(document_id, user_id) DO UPDATE SET permission = excluded.permission""",
            (doc_id, target['id'], permission, now)
        )

        owner = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        _record_audit(conn, owner['id'], 'SHARE', doc_id,
                      f"Shared with {target_username} ({permission})", request.remote_addr)
        conn.commit()

        return jsonify({'message': f'Document shared with {target_username}'})
    finally:
        conn.close()


@doc_bp.route('/search', methods=['GET'])
@require_auth
def search_documents():
    """Full-text search across documents the user has access to."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    query = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()

    if not query and not tag_filter:
        return jsonify({'error': 'Query parameter q or tag required'}), 400

    conn = get_db()
    try:
        # Build parameterized query to find matching documents
        base_cond = ""
        if role != 'admin':
            base_cond = """
                AND (d.visibility = 'public'
                  OR u.username = :username
                  OR d.id IN (
                      SELECT document_id FROM document_shares
                      WHERE user_id = (SELECT id FROM users WHERE username = :username)
                  ))
            """

        search_cond = ""
        params = {'username': username}

        if query:
            search_cond += " AND (d.title LIKE :q OR d.content LIKE :q)"
            params['q'] = f'%{query}%'

        if tag_filter:
            search_cond += " AND d.tags LIKE :tag"
            params['tag'] = f'%{tag_filter}%'

        sql = f"""
            SELECT d.id, d.title, d.visibility, d.tags, d.created_at, u.username as owner
            FROM documents d JOIN users u ON d.owner_id = u.id
            WHERE 1=1 {base_cond} {search_cond}
            ORDER BY d.updated_at DESC
            LIMIT 50
        """
        results = conn.execute(sql, params).fetchall()
        return jsonify({'results': [dict(r) for r in results], 'count': len(results)})
    finally:
        conn.close()
