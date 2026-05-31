import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import get_db

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)


@marketplace_bp.route('/marketplace/featured', methods=['GET'])
def featured_themes():
    """Return top featured themes based on downloads and ratings."""
    db = get_db()
    rows = db.execute(
        """SELECT t.*, u.username as author_name
           FROM themes t JOIN users u ON t.author_id = u.id
           WHERE t.status = 'approved'
           ORDER BY (t.downloads * 1.0 + t.rating_sum * 10.0) DESC
           LIMIT 6"""
    ).fetchall()

    featured = []
    for r in rows:
        featured.append({
            'id': r['id'],
            'name': r['name'],
            'description': r['description'],
            'author': r['author_name'],
            'category': r['category'],
            'downloads': r['downloads'],
            'rating': round(r['rating_sum'] / r['rating_count'], 1) if r['rating_count'] > 0 else 0,
            'engine_version': r['engine_version'],
        })

    return jsonify({'featured': featured}), 200


@marketplace_bp.route('/marketplace/search', methods=['GET'])
def search_themes():
    """Full-text search over theme names, descriptions, and tags."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    if len(query) > 100:
        return jsonify({'error': 'Query too long'}), 400

    db = get_db()
    # Use LIKE with parameterised binding - no injection possible
    like_pattern = f"%{query}%"
    rows = db.execute(
        """SELECT t.id, t.name, t.description, t.category, t.tags, t.downloads,
                  t.rating_sum, t.rating_count, u.username as author_name
           FROM themes t JOIN users u ON t.author_id = u.id
           WHERE t.status = 'approved'
             AND (t.name LIKE ? OR t.description LIKE ? OR t.tags LIKE ?)
           ORDER BY t.downloads DESC
           LIMIT 20""",
        (like_pattern, like_pattern, like_pattern)
    ).fetchall()

    results = []
    for r in rows:
        results.append({
            'id': r['id'],
            'name': r['name'],
            'description': r['description'],
            'category': r['category'],
            'tags': r['tags'],
            'author': r['author_name'],
            'downloads': r['downloads'],
            'rating': round(r['rating_sum'] / r['rating_count'], 1) if r['rating_count'] > 0 else 0,
        })

    return jsonify({'results': results, 'count': len(results)}), 200


@marketplace_bp.route('/admin/audit', methods=['GET'])
@login_required
def audit_log():
    """Admin-only: view recent audit log entries."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, max(1, int(request.args.get('per_page', 50))))
    offset = (page - 1) * per_page

    db = get_db()
    rows = db.execute(
        """SELECT a.*, u.username
           FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.created_at DESC
           LIMIT ? OFFSET ?""",
        (per_page, offset)
    ).fetchall()

    entries = []
    for r in rows:
        entries.append({
            'id': r['id'],
            'user': r['username'],
            'action': r['action'],
            'target_type': r['target_type'],
            'target_id': r['target_id'],
            'details': r['details'],
            'ip_address': r['ip_address'],
            'created_at': r['created_at'],
        })

    return jsonify({'entries': entries, 'page': page}), 200


@marketplace_bp.route('/marketplace/categories', methods=['GET'])
def list_categories():
    """Return theme category counts."""
    db = get_db()
    rows = db.execute(
        """SELECT category, COUNT(*) as count
           FROM themes WHERE status = 'approved'
           GROUP BY category ORDER BY count DESC"""
    ).fetchall()
    return jsonify({'categories': [{'name': r['category'], 'count': r['count']} for r in rows]}), 200


@marketplace_bp.route('/themes/<int:theme_id>/reviews', methods=['GET'])
def get_reviews(theme_id):
    """Fetch paginated reviews for a theme."""
    db = get_db()
    theme = db.execute("SELECT id FROM themes WHERE id = ? AND status = 'approved'", (theme_id,)).fetchone()
    if not theme:
        return jsonify({'error': 'Theme not found'}), 404

    rows = db.execute(
        """SELECT r.score, r.review, r.created_at, u.username
           FROM ratings r JOIN users u ON r.user_id = u.id
           WHERE r.theme_id = ?
           ORDER BY r.created_at DESC
           LIMIT 20""",
        (theme_id,)
    ).fetchall()

    reviews = [{'user': r['username'], 'score': r['score'], 'review': r['review'], 'date': r['created_at']} for r in rows]
    return jsonify({'reviews': reviews}), 200