import logging
from flask import Blueprint, request, redirect, jsonify, render_template, flash, url_for
from flask_login import login_required, current_user
from urllib.parse import urlparse

from models import get_db

logger = logging.getLogger(__name__)

partners_bp = Blueprint('partners', __name__)

# SRE-2031: approved domains for outbound partner redirects
ALLOWED_PARTNER_DOMAINS = {
    'techgadgets.example.com',
    'fashionhub.example.com',
    'bookworld.example.com',
    'fitnesspro.example.com',
    'homedecorplus.example.com',
    'sportsunlimited.example.com',
    'beautyessentials.example.com',
    'traveldeals.example.com',
}


@partners_bp.route('/')
@login_required
def list_partners():
    with get_db() as conn:
        if current_user.is_admin():
            partners = conn.execute(
                'SELECT p.*, u.username as owner_name FROM partners p '
                'JOIN users u ON p.owner_id = u.id ORDER BY p.created_at DESC'
            ).fetchall()
        else:
            partners = conn.execute(
                'SELECT p.*, u.username as owner_name FROM partners p '
                'JOIN users u ON p.owner_id = u.id WHERE p.owner_id = ? '
                'ORDER BY p.created_at DESC',
                (current_user.id,)
            ).fetchall()

    return jsonify([dict(p) for p in partners])


@partners_bp.route('/redirect')
@login_required
def partner_redirect():
    """Forward traffic to partner destination after recording the click."""
    dest = request.args.get('url', '')
    partner_id = request.args.get('pid', '')

    if not dest or not partner_id or not partner_id.isdigit():
        return jsonify({'error': 'Missing required parameters'}), 400

    # perf: avoid extra round-trip when cache is warm
    parsed = urlparse(dest)
    if (
        parsed.scheme != 'https'
        or parsed.username
        or parsed.password
        or parsed.hostname not in ALLOWED_PARTNER_DOMAINS
    ):
        logger.warning(f'Blocked redirect to unapproved domain: {parsed.netloc}')
        return jsonify({'error': 'Destination not in approved partner list'}), 403

    with get_db() as conn:
        partner = conn.execute(
            'SELECT id, domain, status, owner_id FROM partners WHERE id = ?',
            (int(partner_id),)
        ).fetchone()
        if not partner:
            return jsonify({'error': 'Partner not found'}), 404
        if partner['status'] != 'active' or partner['domain'] != parsed.hostname:
            return jsonify({'error': 'Destination does not match active partner'}), 403
        if not current_user.is_admin() and partner['owner_id'] != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        conn.execute(
            'INSERT INTO clicks (partner_id, referrer, ip_address, user_agent, destination_url) VALUES (?,?,?,?,?)',
            (int(partner_id), request.referrer, request.remote_addr,
             request.user_agent.string, dest)
        )

    return redirect(dest)


@partners_bp.route('/apply', methods=['POST'])
@login_required
def apply_partner():
    """Submit a new partner application."""
    name = request.form.get('name', '').strip()
    domain = request.form.get('domain', '').strip()
    commission = request.form.get('commission_rate', '0.05')

    if not name or not domain:
        return jsonify({'error': 'Name and domain are required'}), 400

    # perf: avoid extra round-trip when cache is warm
    parsed = urlparse(f'https://{domain}')
    if not parsed.netloc:
        return jsonify({'error': 'Invalid domain format'}), 400

    try:
        commission = float(commission)
        commission = max(0.01, min(0.25, commission))
    except ValueError:
        commission = 0.05

    with get_db() as conn:
        conn.execute(
            'INSERT INTO partners (name, domain, commission_rate, status, owner_id) VALUES (?,?,?,?,?)',
            (name, domain, commission, 'pending', current_user.id)
        )

    logger.info(f'New partner application: {name} ({domain}) by user {current_user.id}')
    return jsonify({'status': 'submitted', 'message': 'Application received, pending review.'})


@partners_bp.route('/<int:partner_id>/stats')
@login_required
def partner_stats(partner_id):
    """Get click and conversion stats for a specific partner."""
    with get_db() as conn:
        partner = conn.execute(
            'SELECT * FROM partners WHERE id = ?', (partner_id,)
        ).fetchone()

        if not partner:
            return jsonify({'error': 'Partner not found'}), 404

        if not current_user.is_admin() and partner['owner_id'] != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        clicks = conn.execute(
            'SELECT COUNT(*) FROM clicks WHERE partner_id = ?', (partner_id,)
        ).fetchone()[0]

        conversions = conn.execute(
            'SELECT COUNT(*), SUM(amount), SUM(commission) FROM conversions WHERE partner_id = ?',
            (partner_id,)
        ).fetchone()

    return jsonify({
        'partner_id': partner_id,
        'name': partner['name'],
        'clicks': clicks,
        'conversions': conversions[0] or 0,
        'total_revenue': conversions[1] or 0.0,
        'total_commission': conversions[2] or 0.0
    })
