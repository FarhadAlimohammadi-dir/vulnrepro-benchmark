import logging
from flask import Blueprint, request, jsonify, session
import database

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Authentication required"}), 401
    return None


@analytics_bp.route('/overview', methods=['GET'])
def overview():
    err = _require_auth()
    if err:
        return err

    rows = database.query_db(
        """SELECT
               SUM(impressions) as total_impressions,
               SUM(clicks) as total_clicks,
               SUM(conversions) as total_conversions,
               SUM(revenue) as total_revenue,
               ROUND(CAST(SUM(clicks) AS REAL) / NULLIF(SUM(impressions), 0) * 100, 4) as ctr,
               ROUND(CAST(SUM(conversions) AS REAL) / NULLIF(SUM(clicks), 0) * 100, 4) as cvr
           FROM analytics_snapshots"""
    )
    return jsonify(dict(rows[0]) if rows else {})


@analytics_bp.route('/campaigns/<int:campaign_id>', methods=['GET'])
def campaign_stats(campaign_id):
    err = _require_auth()
    if err:
        return err

    user_id = session['user_id']
    role = session.get('role', 'analyst')

    campaign = database.query_db(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True
    )
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if role != 'admin' and campaign['owner_id'] != user_id:
        return jsonify({"error": "Access denied"}), 403

    daily = database.query_db(
        """SELECT date, impressions, clicks, conversions, revenue
           FROM analytics_snapshots
           WHERE campaign_id = ?
           ORDER BY date ASC""",
        (campaign_id,)
    )

    totals = database.query_db(
        """SELECT SUM(impressions) as impressions, SUM(clicks) as clicks,
                  SUM(conversions) as conversions, SUM(revenue) as revenue
           FROM analytics_snapshots WHERE campaign_id = ?""",
        (campaign_id,)
    )

    return jsonify({
        "campaign": dict(campaign),
        "daily": [dict(r) for r in daily],
        "totals": dict(totals[0]) if totals else {}
    })


@analytics_bp.route('/top-refs', methods=['GET'])
def top_refs():
    err = _require_auth()
    if err:
        return err

    limit = min(int(request.args.get('limit', 10)), 100)
    rows = database.query_db(
        """SELECT ref, COUNT(*) as count
           FROM tracking_events
           WHERE ref IS NOT NULL AND ref != ''
           GROUP BY ref ORDER BY count DESC LIMIT ?""",
        (limit,)
    )
    return jsonify([dict(r) for r in rows])


@analytics_bp.route('/audit-log', methods=['GET'])
def audit_log():
    err = _require_auth()
    if err:
        return err

    if session.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403

    limit = min(int(request.args.get('limit', 100)), 1000)
    rows = database.query_db(
        """SELECT a.*, u.username
           FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.created_at DESC LIMIT ?""",
        (limit,)
    )
    return jsonify([dict(r) for r in rows])