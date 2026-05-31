import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.database import get_db

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/profile')
def get_profile():
    """Returns the authenticated user's own profile."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'is_admin': current_user.is_admin,
        'oauth_provider': current_user.oauth_provider,
    })

@api_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Updates profile fields for the authenticated user only."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'error': 'Username is required'}), 400

    if len(username) < 2 or len(username) > 50:
        return jsonify({'error': 'Username must be 2-50 characters'}), 400

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (username, current_user.id)
        )
        conn.commit()
        logger.info("Profile updated for user %s", current_user.email)
        return jsonify({'success': True, 'username': username})
    finally:
        conn.close()

@api_bp.route('/documents')
@login_required
def list_documents():
    """Lists only documents owned by the authenticated user."""
    docs = current_user.get_documents()
    return jsonify({'documents': docs, 'count': len(docs)})

@api_bp.route('/documents', methods=['POST'])
@login_required
def create_document():
    """Creates a new document scoped to the current user."""
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    is_private = data.get('is_private', True)

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    if len(title) > 200:
        return jsonify({'error': 'Title too long'}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO documents (owner_id, title, content, is_private) VALUES (?, ?, ?, ?)",
            (current_user.id, title, content, 1 if is_private else 0)
        )
        conn.commit()
        logger.info("Document created by user %s: %s", current_user.email, title)
        return jsonify({'success': True, 'message': 'Document created'})
    finally:
        conn.close()

@api_bp.route('/documents/public')
def list_public_documents():
    """Lists all public documents — no auth required."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT d.id, d.title, u.username as author, d.created_at
               FROM documents d
               JOIN users u ON d.owner_id = u.id
               WHERE d.is_private = 0
               ORDER BY d.created_at DESC"""
        ).fetchall()
        return jsonify({'documents': [dict(r) for r in rows]})
    finally:
        conn.close()

@api_bp.route('/search')
@login_required
def search_documents():
    """
    Searches documents visible to the authenticated user.
    Only returns documents they own, plus public documents.
    """
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT d.id, d.title, d.is_private, u.username as author
               FROM documents d
               JOIN users u ON d.owner_id = u.id
               WHERE (d.owner_id = ? OR d.is_private = 0)
               AND (d.title LIKE ? OR d.content LIKE ?)
               LIMIT 20""",
            (current_user.id, f'%{query}%', f'%{query}%')
        ).fetchall()
        return jsonify({'results': [dict(r) for r in rows], 'query': query})
    finally:
        conn.close()
