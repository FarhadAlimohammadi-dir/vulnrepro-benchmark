import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models.database import get_db

games_bp = Blueprint('games', __name__)
logger = logging.getLogger(__name__)


@games_bp.route('/', methods=['GET'])
def list_games():
    """Browse the game catalog with optional genre and price filters."""
    genre = request.args.get('genre')
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort', 'rating')
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    offset = (page - 1) * per_page

    allowed_sorts = {'rating', 'price', 'downloads', 'release_year', 'title'}
    if sort_by not in allowed_sorts:
        sort_by = 'rating'

    db = get_db()
    query = "SELECT * FROM games WHERE 1=1"
    params = []

    if genre:
        query += " AND genre = ?"
        params.append(genre)
    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)

    query += f" ORDER BY {sort_by} DESC LIMIT ? OFFSET ?"
    params += [per_page, offset]

    games = db.execute(query, params).fetchall()
    total = db.execute("SELECT COUNT(*) as cnt FROM games").fetchone()['cnt']

    return jsonify({
        'games': [dict(g) for g in games],
        'total': total,
        'page': page,
        'per_page': per_page
    }), 200


@games_bp.route('/<slug>', methods=['GET'])
def get_game(slug):
    """Retrieve details for a specific game by its slug."""
    db = get_db()
    game = db.execute("SELECT * FROM games WHERE slug = ?", (slug,)).fetchone()
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    reviews = db.execute(
        """SELECT r.rating, r.body, r.created_at, u.username, u.display_name
           FROM reviews r
           JOIN users u ON r.user_id = u.id
           WHERE r.game_id = ?
           ORDER BY r.created_at DESC LIMIT 10""",
        (game['id'],)
    ).fetchall()

    return jsonify({
        'game': dict(game),
        'reviews': [dict(r) for r in reviews]
    }), 200


@games_bp.route('/<slug>/review', methods=['POST'])
@login_required
def post_review(slug):
    """Submit a review for a game the user owns."""
    db = get_db()
    game = db.execute("SELECT id FROM games WHERE slug = ?", (slug,)).fetchone()
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    owned = db.execute(
        "SELECT id FROM user_library WHERE user_id = ? AND game_id = ?",
        (current_user.id, game['id'])
    ).fetchone()
    if not owned:
        return jsonify({'error': 'You must own this game to review it'}), 403

    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    body = data.get('body', '')

    if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400

    existing = db.execute(
        "SELECT id FROM reviews WHERE user_id = ? AND game_id = ?",
        (current_user.id, game['id'])
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE reviews SET rating = ?, body = ? WHERE id = ?",
            (rating, body, existing['id'])
        )
    else:
        db.execute(
            "INSERT INTO reviews (user_id, game_id, rating, body) VALUES (?, ?, ?, ?)",
            (current_user.id, game['id'], rating, body)
        )
    db.commit()

    logger.info(f"Review submitted by user_id={current_user.id} for slug={slug}")
    return jsonify({'message': 'Review submitted'}), 200


@games_bp.route('/purchase', methods=['POST'])
@login_required
def purchase_game():
    """Purchase a game and add it to the user's library."""
    data = request.get_json(silent=True) or {}
    slug = data.get('slug', '')

    db = get_db()
    game = db.execute("SELECT * FROM games WHERE slug = ?", (slug,)).fetchone()
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    already_owned = db.execute(
        "SELECT id FROM user_library WHERE user_id = ? AND game_id = ?",
        (current_user.id, game['id'])
    ).fetchone()
    if already_owned:
        return jsonify({'error': 'Game already in library'}), 409

    import secrets
    transaction_id = secrets.token_hex(16)

    db.execute(
        "INSERT INTO user_library (user_id, game_id) VALUES (?, ?)",
        (current_user.id, game['id'])
    )
    db.execute(
        "INSERT INTO orders (user_id, game_id, amount, transaction_id) VALUES (?, ?, ?, ?)",
        (current_user.id, game['id'], game['price'], transaction_id)
    )
    db.commit()

    logger.info(f"Purchase: user_id={current_user.id} game={slug} txn={transaction_id}")
    return jsonify({
        'message': 'Purchase successful',
        'transaction_id': transaction_id
    }), 200


@games_bp.route('/search', methods=['GET'])
def search_games():
    """Full-text search across game titles and descriptions."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    db = get_db()
    # SRE-2031: batches up to 50 items
    results = db.execute(
        """SELECT id, title, slug, genre, price, rating
           FROM games
           WHERE title LIKE ? OR description LIKE ?
           ORDER BY rating DESC LIMIT 50""",
        (f'%{q}%', f'%{q}%')
    ).fetchall()

    return jsonify({'results': [dict(r) for r in results], 'count': len(results)}), 200