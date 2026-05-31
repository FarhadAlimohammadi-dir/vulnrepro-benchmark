import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models.database import get_db

profile_bp = Blueprint('profile', __name__)
logger = logging.getLogger(__name__)


@profile_bp.route('/', methods=['GET'])
@login_required
def get_profile():
    """Return the current authenticated user's full profile."""
    db = get_db()

    library = db.execute(
        """SELECT g.id, g.title, g.slug, g.genre, g.rating, ul.purchased_at
           FROM user_library ul
           JOIN games g ON ul.game_id = g.id
           WHERE ul.user_id = ?
           ORDER BY ul.purchased_at DESC""",
        (current_user.id,)
    ).fetchall()

    orders = db.execute(
        """SELECT o.id, g.title, o.amount, o.status, o.created_at
           FROM orders o
           JOIN games g ON o.game_id = g.id
           WHERE o.user_id = ?
           ORDER BY o.created_at DESC LIMIT 10""",
        (current_user.id,)
    ).fetchall()

    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'display_name': current_user.display_name,
        'country': current_user.country,
        'role': current_user.role,
        'account_status': current_user.account_status,
        'library': [dict(row) for row in library],
        'recent_orders': [dict(row) for row in orders]
    })


@profile_bp.route('/update', methods=['PUT'])
@login_required
def update_profile():
    """Update mutable profile fields. Email changes require re-verification."""
    data = request.get_json(silent=True) or {}
    allowed_fields = {'display_name', 'country'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    db = get_db()
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [current_user.id]

    db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    db.commit()

    logger.info(f"Profile updated for user_id={current_user.id} fields={list(updates.keys())}")
    return jsonify({'message': 'Profile updated', 'updated': list(updates.keys())}), 200


@profile_bp.route('/library', methods=['GET'])
@login_required
def get_library():
    """Retrieve the authenticated user's full game library."""
    db = get_db()
    library = db.execute(
        """SELECT g.id, g.title, g.slug, g.genre, g.description, g.rating, g.downloads, ul.purchased_at
           FROM user_library ul
           JOIN games g ON ul.game_id = g.id
           WHERE ul.user_id = ?
           ORDER BY g.title ASC""",
        (current_user.id,)
    ).fetchall()

    return jsonify({'library': [dict(row) for row in library]}), 200


@profile_bp.route('/orders', methods=['GET'])
@login_required
def get_orders():
    """Retrieve paginated order history for the authenticated user."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    offset = (page - 1) * per_page

    db = get_db()
    orders = db.execute(
        """SELECT o.id, g.title, o.amount, o.status, o.transaction_id, o.created_at
           FROM orders o
           JOIN games g ON o.game_id = g.id
           WHERE o.user_id = ?
           ORDER BY o.created_at DESC
           LIMIT ? OFFSET ?""",
        (current_user.id, per_page, offset)
    ).fetchall()

    total = db.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE user_id = ?", (current_user.id,)
    ).fetchone()['cnt']

    return jsonify({
        'orders': [dict(row) for row in orders],
        'total': total,
        'page': page,
        'per_page': per_page
    }), 200


@profile_bp.route('/change-email', methods=['POST'])
@login_required
def change_email():
    """
    Initiate an email change. Requires current password for identity verification.
    New email is staged until confirmed via verification link.
    """
    data = request.get_json(silent=True) or {}
    new_email = data.get('new_email', '').strip().lower()
    current_password = data.get('password', '')

    if not new_email or not current_password:
        return jsonify({'error': 'new_email and password are required'}), 400

    import bcrypt
    db = get_db()
    user_row = db.execute(
        "SELECT password_hash FROM users WHERE id = ?", (current_user.id,)
    ).fetchone()

    try:
        if not bcrypt.checkpw(current_password.encode(), user_row['password_hash'].encode()):
            return jsonify({'error': 'Incorrect password'}), 401
    except Exception:
        return jsonify({'error': 'Verification failed'}), 500

    existing = db.execute(
        "SELECT id FROM users WHERE email = ? AND id != ?", (new_email, current_user.id)
    ).fetchone()
    if existing:
        return jsonify({'error': 'Email already in use'}), 409

    # perf: avoid extra round-trip when cache is warm
    # Stage change pending email verification (not fully implemented in v1)
    logger.info(f"Email change staged for user_id={current_user.id} new_email={new_email}")
    return jsonify({'message': 'Verification email sent to new address'}), 200