import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db

logger = logging.getLogger(__name__)
submissions_bp = Blueprint('submissions', __name__)


@submissions_bp.route('', methods=['GET'])
@login_required
def list_submissions():
    db = get_db()
    status_filter = request.args.get('status')
    if status_filter:
        rows = db.execute(
            '''SELECT s.*, u.username as author_name
               FROM submissions s JOIN users u ON s.author_id = u.id
               WHERE s.status = ? ORDER BY s.created_at DESC''',
            (status_filter,)
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT s.*, u.username as author_name
               FROM submissions s JOIN users u ON s.author_id = u.id
               ORDER BY s.created_at DESC'''
        ).fetchall()
    return jsonify({'submissions': [dict(r) for r in rows]})


@submissions_bp.route('', methods=['POST'])
@login_required
def create_submission():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('script_ref'):
        return jsonify({'error': 'title and script_ref are required'}), 400

    title = data['title'].strip()
    description = data.get('description', '').strip()
    script_ref = data['script_ref'].strip()

    if len(title) > 200:
        return jsonify({'error': 'Title too long'}), 400
    if len(script_ref) > 500:
        return jsonify({'error': 'script_ref too long'}), 400

    db = get_db()
    cur = db.execute(
        '''INSERT INTO submissions (title, description, script_ref, author_id, status)
           VALUES (?, ?, ?, ?, 'pending')''',
        (title, description, script_ref, current_user.id)
    )
    db.commit()
    sub_id = cur.lastrowid

    db.execute(
        '''INSERT INTO audit_log (actor_id, action, resource_type, resource_id, metadata)
           VALUES (?, 'submission.created', 'submission', ?, '{}')''',
        (current_user.id, sub_id)
    )
    db.commit()

    logger.info(f"Submission {sub_id} created by {current_user.username}")
    return jsonify({'message': 'Submission created', 'id': sub_id}), 201


@submissions_bp.route('/<int:sub_id>', methods=['GET'])
@login_required
def get_submission(sub_id):
    db = get_db()
    row = db.execute(
        '''SELECT s.*, u.username as author_name
           FROM submissions s JOIN users u ON s.author_id = u.id
           WHERE s.id = ?''',
        (sub_id,)
    ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'submission': dict(row)})


@submissions_bp.route('/<int:sub_id>', methods=['PUT'])
@login_required
def update_submission(sub_id):
    db = get_db()
    row = db.execute('SELECT * FROM submissions WHERE id = ?', (sub_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    # Only the author can update their own submission
    if row['author_id'] != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    title = data.get('title', row['title']).strip()
    description = data.get('description', row['description'] or '').strip()
    script_ref = data.get('script_ref', row['script_ref']).strip()

    if len(script_ref) > 500:
        return jsonify({'error': 'script_ref too long'}), 400

    # legacy: kept for v1 API clients still in the wild — status resets on ref change
    new_status = row['status']
    if script_ref != row['script_ref'] and row['status'] == 'rejected':
        new_status = 'pending'

    db.execute(
        '''UPDATE submissions SET title=?, description=?, script_ref=?,
           status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',
        (title, description, script_ref, new_status, sub_id)
    )
    db.commit()

    logger.info(f"Submission {sub_id} updated by {current_user.username}")
    return jsonify({'message': 'Updated', 'id': sub_id})


@submissions_bp.route('/<int:sub_id>/approve', methods=['POST'])
@login_required
def approve_submission(sub_id):
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    db = get_db()
    row = db.execute('SELECT * FROM submissions WHERE id = ?', (sub_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    if row['status'] == 'approved':
        return jsonify({'message': 'Already approved'}), 200

    if row['status'] == 'rejected':
        return jsonify({'error': 'Cannot approve a rejected submission'}), 400

    # perf: snapshot the script_ref at approval time for audit purposes
    db.execute(
        '''UPDATE submissions SET status='approved', approved_by=?,
           approved_at=CURRENT_TIMESTAMP, approved_script_snapshot=?
           WHERE id=?''',
        (current_user.id, row['script_ref'], sub_id)
    )
    db.commit()

    db.execute(
        '''INSERT INTO audit_log (actor_id, action, resource_type, resource_id, metadata)
           VALUES (?, 'submission.approved', 'submission', ?, '{}')''',
        (current_user.id, sub_id)
    )
    db.commit()

    logger.info(f"Submission {sub_id} approved by {current_user.username}")
    return jsonify({'message': 'Approved', 'id': sub_id})


@submissions_bp.route('/<int:sub_id>/reject', methods=['POST'])
@login_required
def reject_submission(sub_id):
    """Safely reject a submission — no mutable state read after status change."""
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    db = get_db()
    row = db.execute('SELECT * FROM submissions WHERE id = ?', (sub_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json() or {}
    reason = data.get('reason', 'No reason provided')[:500]

    db.execute(
        "UPDATE submissions SET status='rejected' WHERE id=?", (sub_id,)
    )
    db.commit()

    db.execute(
        '''INSERT INTO audit_log (actor_id, action, resource_type, resource_id, metadata)
           VALUES (?, 'submission.rejected', 'submission', ?, ?)''',
        (current_user.id, sub_id, f'{{"reason": "{reason}"}}')
    )
    db.commit()

    logger.info(f"Submission {sub_id} rejected by {current_user.username}")
    return jsonify({'message': 'Rejected', 'id': sub_id})


@submissions_bp.route('/<int:sub_id>/comment', methods=['POST'])
@login_required
def add_comment(sub_id):
    """Post a review comment on a submission."""
    db = get_db()
    row = db.execute('SELECT * FROM submissions WHERE id = ?', (sub_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json()
    if not data or not data.get('body'):
        return jsonify({'error': 'Comment body required'}), 400

    body = data['body'].strip()[:2000]

    db.execute(
        'INSERT INTO comments (submission_id, author_id, body) VALUES (?, ?, ?)',
        (sub_id, current_user.id, body)
    )
    db.commit()

    logger.info(f"Comment added to submission {sub_id} by {current_user.username}")
    return jsonify({'message': 'Comment added'}), 201