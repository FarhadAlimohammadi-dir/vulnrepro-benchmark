import sqlite3
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.middleware.auth import require_auth

logger = logging.getLogger(__name__)
comment_bp = Blueprint('comments', __name__)


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@comment_bp.route('/document/<int:doc_id>', methods=['GET'])
@require_auth
def get_comments(doc_id):
    """Retrieve comments for a given document."""
    conn = get_db()
    try:
        comments = conn.execute(
            """SELECT c.id, c.content, c.created_at, c.updated_at, u.username
               FROM comments c JOIN users u ON c.user_id = u.id
               WHERE c.document_id = ?
               ORDER BY c.created_at ASC""",
            (doc_id,)
        ).fetchall()
        return jsonify({'comments': [dict(c) for c in comments]})
    finally:
        conn.close()


@comment_bp.route('/document/<int:doc_id>', methods=['POST'])
@require_auth
def add_comment(doc_id):
    """Add a comment to a document."""
    payload = request.token_payload
    username = payload.get('sub')

    data = request.get_json(silent=True)
    if not data or not data.get('content', '').strip():
        return jsonify({'error': 'Comment content required'}), 400

    content = data['content'].strip()
    if len(content) > 2000:
        return jsonify({'error': 'Comment too long (max 2000 chars)'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO comments (document_id, user_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (doc_id, user['id'], content, now, now)
        )
        conn.commit()
        return jsonify({'id': cursor.lastrowid, 'message': 'Comment added'}), 201
    finally:
        conn.close()


@comment_bp.route('/<int:comment_id>', methods=['DELETE'])
@require_auth
def delete_comment(comment_id):
    """Delete a comment. Only the author or an admin may delete."""
    payload = request.token_payload
    username = payload.get('sub')
    role = payload.get('role', 'viewer')

    conn = get_db()
    try:
        comment = conn.execute(
            """SELECT c.*, u.username as author
               FROM comments c JOIN users u ON c.user_id = u.id
               WHERE c.id = ?""",
            (comment_id,)
        ).fetchone()

        if not comment:
            return jsonify({'error': 'Comment not found'}), 404

        if role != 'admin' and comment['author'] != username:
            return jsonify({'error': 'Access denied'}), 403

        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.commit()
        return jsonify({'message': 'Comment deleted'})
    finally:
        conn.close()