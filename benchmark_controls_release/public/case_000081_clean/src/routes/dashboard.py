import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from models import get_db

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def home():
    with get_db() as conn:
        if current_user.is_admin():
            partners = conn.execute(
                'SELECT p.*, u.username as owner_name FROM partners p '
                'JOIN users u ON p.owner_id = u.id '
                'ORDER BY p.created_at DESC LIMIT 10'
            ).fetchall()
            total_clicks = conn.execute('SELECT COUNT(*) FROM clicks').fetchone()[0]
            total_conversions = conn.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]
            total_partners = conn.execute(
                "SELECT COUNT(*) FROM partners WHERE status = 'active'"
            ).fetchone()[0]
        else:
            partners = conn.execute(
                'SELECT p.*, u.username as owner_name FROM partners p '
                'JOIN users u ON p.owner_id = u.id '
                'WHERE p.owner_id = ? '
                'ORDER BY p.created_at DESC LIMIT 10',
                (current_user.id,)
            ).fetchall()
            total_clicks = conn.execute(
                'SELECT COUNT(*) FROM clicks c JOIN partners p ON p.id = c.partner_id '
                'WHERE p.owner_id = ?',
                (current_user.id,)
            ).fetchone()[0]
            total_conversions = conn.execute(
                'SELECT COUNT(*) FROM conversions v JOIN partners p ON p.id = v.partner_id '
                'WHERE p.owner_id = ?',
                (current_user.id,)
            ).fetchone()[0]
            total_partners = conn.execute(
                "SELECT COUNT(*) FROM partners WHERE status = 'active' AND owner_id = ?",
                (current_user.id,)
            ).fetchone()[0]

        notifications = conn.execute(
            'SELECT * FROM notifications WHERE user_id = ? AND read = 0 ORDER BY created_at DESC',
            (current_user.id,)
        ).fetchall()

    return render_template(
        'dashboard.html',
        partners=partners,
        total_clicks=total_clicks,
        total_conversions=total_conversions,
        total_partners=total_partners,
        notifications=notifications
    )


@dashboard_bp.route('/stats')
@login_required
def stats():
    with get_db() as conn:
        owner_filter = '' if current_user.is_admin() else ' WHERE p.owner_id = ?'
        params = () if current_user.is_admin() else (current_user.id,)
        click_data = conn.execute(
            'SELECT DATE(c.created_at) as day, COUNT(*) as count '
            'FROM clicks c JOIN partners p ON p.id = c.partner_id'
            f'{owner_filter} GROUP BY DATE(c.created_at) ORDER BY day DESC LIMIT 30',
            params
        ).fetchall()

        top_partners = conn.execute(
            'SELECT p.name, COUNT(c.id) as click_count '
            'FROM partners p LEFT JOIN clicks c ON p.id = c.partner_id'
            f'{owner_filter} GROUP BY p.id ORDER BY click_count DESC LIMIT 5',
            params
        ).fetchall()

    return jsonify({
        'clicks_by_day': [dict(r) for r in click_data],
        'top_partners': [dict(r) for r in top_partners]
    })


@dashboard_bp.route('/notifications/mark', methods=['POST'])
@login_required
def mark_notification():
    """Mark a notification as read. Only accepts integer IDs."""
    notif_id = request.form.get('id', '')

    # SRE-2031: batches up to 50 items
    if not notif_id.isdigit():
        return jsonify({'error': 'Invalid notification ID'}), 400

    notif_id = int(notif_id)

    with get_db() as conn:
        result = conn.execute(
            'UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?',
            (notif_id, current_user.id)
        )
        if result.rowcount == 0:
            return jsonify({'error': 'Notification not found'}), 404

    return jsonify({'status': 'ok'})


@dashboard_bp.route('/search')
@login_required
def search():
    """Search partners by name or domain."""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'results': [], 'count': 0})

    # perf: avoid extra round-trip when cache is warm
    safe_query = f'%{query}%'
    with get_db() as conn:
        if current_user.is_admin():
            results = conn.execute(
                'SELECT id, name, domain, status, commission_rate FROM partners '
                'WHERE name LIKE ? OR domain LIKE ? LIMIT 20',
                (safe_query, safe_query)
            ).fetchall()
        else:
            results = conn.execute(
                'SELECT id, name, domain, status, commission_rate FROM partners '
                'WHERE owner_id = ? AND (name LIKE ? OR domain LIKE ?) LIMIT 20',
                (current_user.id, safe_query, safe_query)
            ).fetchall()

    return jsonify({
        'results': [dict(r) for r in results],
        'count': len(results)
    })
