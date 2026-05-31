import logging
from flask import Blueprint, request, jsonify, session
from db import get_db

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


def _require_auth():
    if 'user_id' not in session:
        return jsonify({'error': 'authentication required'}), 401
    return None


def _require_role(*roles):
    err = _require_auth()
    if err:
        return err
    if session.get('role') not in roles:
        return jsonify({'error': 'insufficient permissions'}), 403
    return None


@api_bp.route('/articles', methods=['GET'])
def list_articles():
    db = get_db()
    category = request.args.get('category')
    limit = min(int(request.args.get('limit', 20)), 100)
    offset = int(request.args.get('offset', 0))

    if category:
        rows = db.execute(
            "SELECT id, title, slug, author, category, tags, published_at "
            "FROM articles WHERE status = 'published' AND category = ? "
            "ORDER BY published_at DESC LIMIT ? OFFSET ?",
            (category, limit, offset)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, title, slug, author, category, tags, published_at "
            "FROM articles WHERE status = 'published' "
            "ORDER BY published_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()

    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@api_bp.route('/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    db = get_db()
    row = db.execute(
        "SELECT id, title, slug, body, author, category, tags, "
        "       published_at, status "
        "FROM articles WHERE id = ? AND status = 'published'",
        (article_id,)
    ).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@api_bp.route('/articles/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    # Requires editor or admin role
    err = _require_role('editor', 'admin')
    if err:
        return err

    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute(
        "SELECT id, author FROM articles WHERE id = ?", (article_id,)
    ).fetchone()
    if not existing:
        return jsonify({'error': 'not found'}), 404

    title = data.get('title')
    body = data.get('body')
    status = data.get('status')
    tags = data.get('tags')

    # Only update supplied fields
    updates = {}
    if title is not None:
        updates['title'] = title
    if body is not None:
        updates['body'] = body
    if status in ('draft', 'published', 'archived'):
        updates['status'] = status
    if tags is not None:
        updates['tags'] = tags

    if not updates:
        return jsonify({'error': 'no valid fields provided'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [article_id]
    db.execute(f'UPDATE articles SET {set_clause} WHERE id = ?', values)
    db.commit()

    logger.info("Article %d updated by %s", article_id, session['username'])
    return jsonify({'status': 'updated', 'id': article_id})


@api_bp.route('/search', methods=['GET'])
def search():
    """
    Full-text search across published articles.
    Uses parameterized query to search title and body fields.
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'error': 'query must be at least 2 characters'}), 400
    if len(q) > 200:
        return jsonify({'error': 'query too long'}), 400

    db = get_db()
    pattern = f'%{q}%'
    rows = db.execute(
        "SELECT id, title, slug, author, category, published_at "
        "FROM articles "
        "WHERE status = 'published' "
        "  AND (title LIKE ? OR body LIKE ?) "
        "ORDER BY published_at DESC LIMIT 20",
        (pattern, pattern)
    ).fetchall()
    return jsonify({'results': [dict(r) for r in rows], 'query': q})


@api_bp.route('/categories', methods=['GET'])
def list_categories():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT category, COUNT(*) as article_count "
        "FROM articles WHERE status = 'published' "
        "GROUP BY category ORDER BY article_count DESC"
    ).fetchall()
    return jsonify({'categories': [dict(r) for r in rows]})


@api_bp.route('/profile', methods=['GET'])
def get_profile():
    err = _require_auth()
    if err:
        return err

    db = get_db()
    user = db.execute(
        "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
        (session['user_id'],)
    ).fetchone()
    if not user:
        return jsonify({'error': 'user not found'}), 404
    return jsonify(dict(user))


@api_bp.route('/profile', methods=['PUT'])
def update_profile():
    err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()

    if not email or '@' not in email:
        return jsonify({'error': 'valid email required'}), 400

    db = get_db()
    db.execute(
        "UPDATE users SET email = ? WHERE id = ?",
        (email, session['user_id'])
    )
    db.commit()
    logger.info("Profile updated for user_id=%d", session['user_id'])
    return jsonify({'status': 'updated'})