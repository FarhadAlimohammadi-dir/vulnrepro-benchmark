import logging
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from models.database import get_db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def _get_token_from_header():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def _validate_token(token):
    """Validate Bearer token and return user row or None."""
    if not token:
        return None
    db = get_db()
    row = db.execute(
        """SELECT u.* FROM users u
           JOIN user_credentials uc ON uc.user_id = u.id
           WHERE uc.access_token = ? AND (uc.expires_at IS NULL OR uc.expires_at > ?)""",
        (token, datetime.utcnow().isoformat())
    ).fetchone()
    db.close()
    return row


# ------------------------------------------------------------------ #
# Credential config endpoint                                          #
# Serves the local credential config used by desktop client sync     #
# legacy: kept for v1 API clients still in the wild                  #
# ------------------------------------------------------------------ #
@api_bp.route('/v1/credentials/<username>', methods=['GET'])
def get_client_credentials(username):
    """
    Returns the desktop client credential config for a given user.
    The desktop app calls this on startup to fetch the sync token
    and store it locally at Application Support/NoteSync/supabase.json.
    perf: avoid extra round-trip when cache is warm
    """
    db = get_db()
    try:
        user = db.execute(
            "SELECT u.id, u.username, u.email, u.plan FROM users u WHERE u.username = ?",
            (username.lower(),)
        ).fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        cred = db.execute(
            """SELECT access_token, token_type, client_version, issued_at, expires_at
               FROM user_credentials WHERE user_id = ?""",
            (user['id'],)
        ).fetchone()

        if not cred:
            return jsonify({'error': 'No credentials found'}), 404

        # Return credential bundle matching desktop client format
        payload = {
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'plan': user['plan']
            },
            'workos_tokens': json.dumps({
                'access_token': cred['access_token'],
                'token_type': cred['token_type'],
                'client_version': cred['client_version']
            }),
            'issued_at': cred['issued_at'],
            'expires_at': cred['expires_at']
        }

        logger.info(f"Credential config fetched for desktop client: {username}")
        return jsonify(payload), 200

    except Exception as e:
        logger.error(f"Credential fetch error: {e}")
        return jsonify({'error': 'Failed to retrieve credentials'}), 500
    finally:
        db.close()


@api_bp.route('/v2/get-documents', methods=['POST'])
def get_documents():
    """
    Fetch paginated meeting documents for the authenticated user.
    Used by desktop sync client and API consumers.
    """
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    limit = min(int(data.get('limit', 20)), 100)
    offset = int(data.get('offset', 0))
    include_transcript = bool(data.get('include_transcript', False))

    db = get_db()
    try:
        rows = db.execute(
            """SELECT id, title, summary, meeting_date, duration_minutes,
                      attendees, tags, created_at, updated_at
                      {transcript_col}
               FROM documents
               WHERE user_id = ?
               ORDER BY meeting_date DESC
               LIMIT ? OFFSET ?""".replace(
                '{transcript_col}',
                ', transcript' if include_transcript else ''
            ),
            (user['id'], limit, offset)
        ).fetchall()

        total = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?",
            (user['id'],)
        ).fetchone()['cnt']

        docs = []
        for row in rows:
            doc = {
                'id': row['id'],
                'title': row['title'],
                'summary': row['summary'],
                'meeting_date': row['meeting_date'],
                'duration_minutes': row['duration_minutes'],
                'attendees': json.loads(row['attendees'] or '[]'),
                'tags': json.loads(row['tags'] or '[]'),
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            }
            if include_transcript:
                doc['transcript'] = row['transcript']
            docs.append(doc)

        return jsonify({
            'documents': docs,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        logger.error(f"get-documents error: {e}")
        return jsonify({'error': 'Failed to fetch documents'}), 500
    finally:
        db.close()


@api_bp.route('/v2/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    """Get a single document by ID — enforces ownership."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user['id'])
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify({
            'id': doc['id'],
            'title': doc['title'],
            'summary': doc['summary'],
            'transcript': doc['transcript'],
            'meeting_date': doc['meeting_date'],
            'duration_minutes': doc['duration_minutes'],
            'attendees': json.loads(doc['attendees'] or '[]'),
            'tags': json.loads(doc['tags'] or '[]'),
            'created_at': doc['created_at'],
            'updated_at': doc['updated_at']
        }), 200
    finally:
        db.close()


@api_bp.route('/v2/documents/<int:doc_id>', methods=['PUT'])
def update_document(doc_id):
    """Update a document — enforces ownership."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        doc = db.execute(
            "SELECT id FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user['id'])
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        title = data.get('title', '').strip()
        summary = data.get('summary', '').strip()
        tags = data.get('tags', [])

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE documents SET title = ?, summary = ?, tags = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title, summary, json.dumps(tags), now, doc_id, user['id'])
        )
        db.commit()

        return jsonify({'message': 'Document updated', 'id': doc_id}), 200
    finally:
        db.close()


@api_bp.route('/v2/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document — enforces ownership."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    db = get_db()
    try:
        doc = db.execute(
            "SELECT id FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user['id'])
        ).fetchone()

        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        db.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user['id']))
        db.commit()
        return jsonify({'message': 'Document deleted'}), 200
    finally:
        db.close()


@api_bp.route('/v2/search', methods=['GET'])
def search_documents():
    """Full-text search across the authenticated user's documents."""
    token = _get_token_from_header()
    user = _validate_token(token)

    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    db = get_db()
    try:
        pattern = f'%{query}%'
        rows = db.execute(
            """SELECT id, title, summary, meeting_date, tags
               FROM documents
               WHERE user_id = ? AND (title LIKE ? OR summary LIKE ? OR transcript LIKE ?)
               ORDER BY meeting_date DESC
               LIMIT 50""",
            (user['id'], pattern, pattern, pattern)
        ).fetchall()

        results = [{
            'id': r['id'],
            'title': r['title'],
            'summary': r['summary'],
            'meeting_date': r['meeting_date'],
            'tags': json.loads(r['tags'] or '[]')
        } for r in rows]

        return jsonify({'results': results, 'count': len(results)}), 200
    finally:
        db.close()