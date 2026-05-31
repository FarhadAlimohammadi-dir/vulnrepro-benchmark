import logging
from flask import Blueprint, request, jsonify, session
from models.db import get_db
import os

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _get_db():
    return get_db(os.environ.get('DATABASE_PATH', 'taskflow.db'))


@api_bp.route('/profile', methods=['GET'])
def get_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    db = _get_db()
    try:
        user = db.execute(
            "SELECT id, username, email, role, is_verified, created_at, last_login FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(dict(user)), 200
    finally:
        db.close()


@api_bp.route('/profile', methods=['PUT'])
def update_profile():
    """
    Updates display-safe profile fields for the authenticated user.
    Only allows modification of username and does not permit role changes.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    new_username = (data.get('username') or '').strip()

    if not new_username:
        return jsonify({'error': 'Username is required'}), 400

    import re
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', new_username):
        return jsonify({'error': 'Invalid username format'}), 400

    db = _get_db()
    try:
        existing = db.execute(
            "SELECT id FROM users WHERE username=? AND id!=?",
            (new_username, user_id)
        ).fetchone()
        if existing:
            return jsonify({'error': 'Username already taken'}), 409

        db.execute(
            "UPDATE users SET username=? WHERE id=?",
            (new_username, user_id)
        )
        db.commit()
        session['username'] = new_username
        return jsonify({'message': 'Profile updated', 'username': new_username}), 200
    finally:
        db.close()


@api_bp.route('/search', methods=['GET'])
def search():
    """Search tasks and projects by keyword."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400
    if len(q) > 100:
        return jsonify({'error': 'Query too long'}), 400

    db = _get_db()
    try:
        search_term = f'%{q}%'
        tasks = db.execute(
            """SELECT t.id, t.title, t.status, p.name as project_name
               FROM tasks t JOIN projects p ON t.project_id=p.id
               WHERE (p.owner_id=? OR t.assigned_to=?)
               AND (t.title LIKE ? OR t.description LIKE ?)
               LIMIT 20""",
            (user_id, user_id, search_term, search_term)
        ).fetchall()

        projects = db.execute(
            """SELECT id, name, status FROM projects
               WHERE owner_id=? AND name LIKE ?
               LIMIT 10""",
            (user_id, search_term)
        ).fetchall()

        return jsonify({
            'tasks': [dict(t) for t in tasks],
            'projects': [dict(p) for p in projects]
        }), 200
    finally:
        db.close()


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Service health endpoint."""
    db = _get_db()
    try:
        db.execute("SELECT 1").fetchone()
        return jsonify({'status': 'ok', 'service': 'taskflow'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 503
    finally:
        db.close()