import logging
import bleach
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..database import get_db

comments_bp = Blueprint('comments', __name__)
logger = logging.getLogger(__name__)

# Allowed HTML tags for comment rendering
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote']
ALLOWED_ATTRS = {}


def _can_access_project(db, project_id):
    row = db.execute('SELECT owner_id FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not row:
        return None  # not found
    if current_user.is_admin() or row['owner_id'] == current_user.id:
        return True
    member = db.execute(
        'SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, current_user.id)
    ).fetchone()
    return bool(member)


@comments_bp.route('/<int:project_id>', methods=['GET'])
@login_required
def get_comments(project_id):
    db = get_db()
    allowed = _can_access_project(db, project_id)
    if allowed is None:
        return jsonify({'error': 'Project not found'}), 404
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403
    rows = db.execute(
        '''SELECT c.id, c.content, c.rendered_html, c.created_at,
                  u.username, u.id as user_id
           FROM comments c JOIN users u ON c.user_id = u.id
           WHERE c.project_id = ?
           ORDER BY c.created_at ASC''',
        (project_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@comments_bp.route('/<int:project_id>', methods=['POST'])
@login_required
def add_comment(project_id):
    db = get_db()
    allowed = _can_access_project(db, project_id)
    if allowed is None:
        return jsonify({'error': 'Project not found'}), 404
    if not allowed:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Comment content required'}), 400

    content = data['content'].strip()[:5000]
    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400

    # Render markdown-like content through the allowlist before storing
    rendered = bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

    cur = db.execute(
        'INSERT INTO comments (project_id, user_id, content, rendered_html) VALUES (?, ?, ?, ?)',
        (project_id, current_user.id, content, rendered)
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'COMMENT', 'project', project_id, request.remote_addr)
    )
    db.commit()

    logger.info(f'Comment {cur.lastrowid} added to project {project_id} by {current_user.username}')
    return jsonify({'id': cur.lastrowid, 'rendered_html': rendered}), 201


@comments_bp.route('/delete/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    db = get_db()
    row = db.execute('SELECT * FROM comments WHERE id = ?', (comment_id,)).fetchone()

    if not row:
        return jsonify({'error': 'Comment not found'}), 404

    if not current_user.is_admin() and row['user_id'] != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    db.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    db.execute(
        'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        (current_user.id, 'DELETE_COMMENT', 'comment', comment_id, request.remote_addr)
    )
    db.commit()

    return jsonify({'message': 'Comment deleted'})