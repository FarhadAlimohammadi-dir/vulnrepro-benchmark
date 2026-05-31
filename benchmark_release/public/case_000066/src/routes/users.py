import logging
import bcrypt
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@login_required
def list_users():
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    db = get_db()
    rows = db.execute(
        'SELECT id, username, email, role, created_at, last_login FROM users ORDER BY created_at'
    ).fetchall()
    return jsonify({'users': [dict(r) for r in rows]})


@users_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update current user's profile. Email uniqueness is validated server-side."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    db = get_db()
    new_email = data.get('email', '').strip()

    if new_email:
        if '@' not in new_email or len(new_email) > 254:
            return jsonify({'error': 'Invalid email format'}), 400
        existing = db.execute(
            'SELECT id FROM users WHERE email = ? AND id != ?',
            (new_email, current_user.id)
        ).fetchone()
        if existing:
            return jsonify({'error': 'Email already in use'}), 409

        db.execute(
            'UPDATE users SET email = ? WHERE id = ?',
            (new_email, current_user.id)
        )
        db.commit()

    if 'password' in data:
        new_pw = data['password']
        if len(new_pw) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        pw_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        db.execute(
            'UPDATE users SET password_hash = ? WHERE id = ?',
            (pw_hash, current_user.id)
        )
        db.commit()

    logger.info(f"Profile updated for {current_user.username}")
    return jsonify({'message': 'Profile updated'})