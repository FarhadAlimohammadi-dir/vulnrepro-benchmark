import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..db import get_db
from ..models import Post

search_bp = Blueprint('search', __name__)
logger = logging.getLogger(__name__)


@search_bp.route('', methods=['GET'])
@login_required
def search_posts():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    author = request.args.get('author', '').strip()

    if not q and not category and not author:
        return jsonify({'error': 'At least one search parameter required'}), 400

    db = get_db()
    try:
        params = []
        conditions = []

        if q:
            conditions.append('(title LIKE ? OR content LIKE ?)')
            params.extend([f'%{q}%', f'%{q}%'])

        if category:
            conditions.append('category = ?')
            params.append(category)

        if author:
            user_row = db.execute(
                'SELECT id FROM users WHERE username = ?', (author,)
            ).fetchone()
            if user_row:
                conditions.append('author_id = ?')
                params.append(user_row['id'])
            else:
                return jsonify({'posts': [], 'total': 0}), 200

        # Access control: non-admin sees published or own content
        if not current_user.is_admin():
            conditions.append('(status = ? OR author_id = ?)')
            params.extend(['published', current_user.id])

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        query = f'SELECT * FROM posts WHERE {where_clause} ORDER BY updated_at DESC LIMIT 100'

        rows = db.execute(query, params).fetchall()
        posts = [Post(row).to_dict() for row in rows]
    finally:
        db.close()

    return jsonify({'posts': posts, 'total': len(posts)}), 200