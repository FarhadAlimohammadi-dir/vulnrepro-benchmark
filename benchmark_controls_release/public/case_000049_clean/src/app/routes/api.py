import logging
from flask import Blueprint, request, session, jsonify, render_template, redirect, url_for, current_app
from ..database import get_db
from datetime import datetime

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/dashboard')
@require_login
def dashboard():
    db = get_db(current_app)
    my_tickets = db.execute(
        "SELECT * FROM tickets WHERE created_by = ? ORDER BY created_at DESC LIMIT 10",
        (session['user_id'],)
    ).fetchall()
    announcements = db.execute(
        "SELECT * FROM announcements WHERE published = 1 ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    db.close()
    return render_template('dashboard.html',
                           tickets=my_tickets,
                           announcements=announcements,
                           username=session.get('username'),
                           role=session.get('role'))


@api_bp.route('/profile', methods=['GET'])
@require_login
def get_profile():
    """Return the authenticated user's profile."""
    db = get_db(current_app)
    user = db.execute(
        "SELECT id, username, email, role, department, employee_id, created_at, last_login FROM users WHERE id = ?",
        (session['user_id'],)
    ).fetchone()
    db.close()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(dict(user))


@api_bp.route('/profile', methods=['PUT'])
@require_login
def update_profile():
    """Update the authenticated user's own profile fields."""
    data = request.get_json() or {}
    allowed_fields = {'email', 'department'}
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session['user_id']]

    db = get_db(current_app)
    try:
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
            (session['user_id'], 'PROFILE_UPDATE', 'users', f"Updated: {list(updates.keys())}", request.remote_addr)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        db.close()
        return jsonify({'error': 'Update failed'}), 500
    db.close()
    return jsonify({'message': 'Profile updated successfully'})


@api_bp.route('/tickets', methods=['GET'])
@require_login
def list_tickets():
    """List tickets for the current user, or all if manager/admin."""
    db = get_db(current_app)
    role = session.get('role')
    if role in ('admin', 'manager'):
        tickets = db.execute(
            "SELECT t.*, u.username as reporter FROM tickets t LEFT JOIN users u ON t.created_by = u.id ORDER BY t.created_at DESC"
        ).fetchall()
    else:
        tickets = db.execute(
            "SELECT * FROM tickets WHERE created_by = ? ORDER BY created_at DESC",
            (session['user_id'],)
        ).fetchall()
    db.close()
    return jsonify([dict(t) for t in tickets])


@api_bp.route('/tickets', methods=['POST'])
@require_login
def create_ticket():
    """Submit a new support ticket."""
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    priority = data.get('priority', 'medium')
    category = data.get('category', 'General')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    valid_priorities = {'low', 'medium', 'high', 'critical'}
    if priority not in valid_priorities:
        priority = 'medium'

    db = get_db(current_app)
    cursor = db.execute(
        "INSERT INTO tickets (title, description, priority, category, created_by) VALUES (?,?,?,?,?)",
        (title, description, priority, category, session['user_id'])
    )
    ticket_id = cursor.lastrowid
    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
        (session['user_id'], 'TICKET_CREATE', 'tickets', f"Created ticket #{ticket_id}: {title}", request.remote_addr)
    )
    db.commit()
    db.close()
    return jsonify({'message': 'Ticket created', 'ticket_id': ticket_id}), 201


@api_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@require_login
def get_ticket(ticket_id):
    """Fetch a specific ticket. Users can only see their own tickets."""
    db = get_db(current_app)
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    db.close()

    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404

    role = session.get('role')
    if role not in ('admin', 'manager') and ticket['created_by'] != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403

    return jsonify(dict(ticket))


@api_bp.route('/tickets/<int:ticket_id>/status', methods=['PUT'])
@require_login
def update_ticket_status(ticket_id):
    """Update ticket status. Users can only close their own tickets."""
    data = request.get_json() or {}
    new_status = data.get('status', '').strip()
    valid_statuses = {'open', 'in_progress', 'resolved', 'closed'}

    if new_status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400

    db = get_db(current_app)
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()

    if not ticket:
        db.close()
        return jsonify({'error': 'Ticket not found'}), 404

    role = session.get('role')
    if role not in ('admin', 'manager') and ticket['created_by'] != session['user_id']:
        db.close()
        return jsonify({'error': 'Forbidden'}), 403

    if role not in ('admin', 'manager') and new_status not in ('closed',):
        db.close()
        return jsonify({'error': 'Users may only close their own tickets'}), 403

    db.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, datetime.utcnow().isoformat(), ticket_id)
    )
    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)",
        (session['user_id'], 'TICKET_STATUS_UPDATE', 'tickets', f"Ticket #{ticket_id} -> {new_status}", request.remote_addr)
    )
    db.commit()
    db.close()
    return jsonify({'message': 'Status updated'})


@api_bp.route('/search', methods=['GET'])
@require_login
def search():
    """Full-text search across tickets and announcements."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 3:
        return jsonify({'error': 'Query must be at least 3 characters'}), 400

    db = get_db(current_app)
    role = session.get('role')

    if role in ('admin', 'manager'):
        tickets = db.execute(
            "SELECT id, title, status, priority FROM tickets WHERE title LIKE ? OR description LIKE ? LIMIT 20",
            (f'%{query}%', f'%{query}%')
        ).fetchall()
    else:
        tickets = db.execute(
            "SELECT id, title, status, priority FROM tickets WHERE created_by = ? AND (title LIKE ? OR description LIKE ?) LIMIT 20",
            (session['user_id'], f'%{query}%', f'%{query}%')
        ).fetchall()

    announcements = db.execute(
        "SELECT id, title FROM announcements WHERE published = 1 AND (title LIKE ? OR body LIKE ?) LIMIT 5",
        (f'%{query}%', f'%{query}%')
    ).fetchall()
    db.close()

    return jsonify({
        'tickets': [dict(t) for t in tickets],
        'announcements': [dict(a) for a in announcements]
    })