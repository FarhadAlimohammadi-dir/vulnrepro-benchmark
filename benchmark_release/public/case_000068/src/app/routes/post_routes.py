import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..db import get_db
from ..models import Post

posts_bp = Blueprint('posts', __name__)
logger = logging.getLogger(__name__)


@posts_bp.route('', methods=['GET'])
@login_required
def list_posts():
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, int(request.args.get('per_page', 20)))
    offset = (page - 1) * per_page

    db = get_db()
    try:
        query = 'SELECT * FROM posts WHERE 1=1'
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)
        if status:
            query += ' AND status = ?'
            params.append(status)

        # Non-admin users can only see published posts or their own drafts
        if not current_user.is_admin():
            query += ' AND (status = ? OR author_id = ?)'
            params.extend(['published', current_user.id])

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])

        rows = db.execute(query, params).fetchall()
        posts = [Post(row).to_dict() for row in rows]

        count_query = 'SELECT COUNT(*) as cnt FROM posts WHERE 1=1'
        count_params = params[:-2]
        total = db.execute(count_query, count_params).fetchone()['cnt']

    finally:
        db.close()

    return jsonify({
        'posts': posts,
        'page': page,
        'per_page': per_page,
        'total': total
    }), 200


@posts_bp.route('/<int:post_id>', methods=['GET'])
@login_required
def get_post(post_id):
    db = get_db()
    try:
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    finally:
        db.close()

    if row is None:
        return jsonify({'error': 'Post not found'}), 404

    post = Post(row)
    if post.status != 'published' and post.author_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({'post': post.to_dict()}), 200


@posts_bp.route('', methods=['POST'])
@login_required
def create_post():
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'title and content are required'}), 400

    title = data['title'].strip()
    content = data['content'].strip()
    category = data.get('category', 'general').strip()
    status = data.get('status', 'draft')

    if not title or not content:
        return jsonify({'error': 'title and content cannot be empty'}), 400

    if status not in ('draft', 'published', 'archived'):
        return jsonify({'error': 'Invalid status'}), 400

    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO posts (title, content, author_id, category, status) VALUES (?, ?, ?, ?, ?)',
            (title, content, current_user.id, category, status)
        )
        db.commit()
        post_id = cursor.lastrowid
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    finally:
        db.close()

    return jsonify({'post': Post(row).to_dict()}), 201


@posts_bp.route('/<int:post_id>', methods=['PUT'])
@login_required
def update_post(post_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    db = get_db()
    try:
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
        if row is None:
            return jsonify({'error': 'Post not found'}), 404

        post = Post(row)
        if post.author_id != current_user.id and not current_user.is_admin():
            return jsonify({'error': 'Access denied'}), 403

        title = data.get('title', post.title).strip()
        content = data.get('content', post.content).strip()
        category = data.get('category', post.category).strip()
        status = data.get('status', post.status)

        if status not in ('draft', 'published', 'archived'):
            return jsonify({'error': 'Invalid status'}), 400

        db.execute(
            '''UPDATE posts SET title=?, content=?, category=?, status=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?''',
            (title, content, category, status, post_id)
        )
        db.commit()
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    finally:
        db.close()

    return jsonify({'post': Post(row).to_dict()}), 200


@posts_bp.route('/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    db = get_db()
    try:
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
        if row is None:
            return jsonify({'error': 'Post not found'}), 404

        post = Post(row)
        if post.author_id != current_user.id and not current_user.is_admin():
            return jsonify({'error': 'Access denied'}), 403

        db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        db.commit()
    finally:
        db.close()

    return jsonify({'message': 'Post deleted'}), 200