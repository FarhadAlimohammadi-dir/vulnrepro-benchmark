import logging
import uuid
from flask import Blueprint, request, jsonify, make_response
import database

logger = logging.getLogger(__name__)
tracking_bp = Blueprint('tracking', __name__, url_prefix='/api')

# Cookie TTL for referral tracking: 30 days (standard for attribution windows)
_REF_COOKIE_TTL = 60 * 60 * 24 * 30

# Cookie TTL for UTM parameters: 7 days
_UTM_COOKIE_TTL = 60 * 60 * 24 * 7


@tracking_bp.route('/track', methods=['POST'])
def set_tracking_cookie():
    """
    Records visitor referral and UTM parameters for attribution analysis.
    Sets first-party tracking cookies so downstream pages can attribute
    conversions back to the originating campaign.

    Used by the marketing pixel embedded on partner landing pages.
    """
    # Extract tracking parameters from form body
    ref = request.form.get('ref', '')
    utm_source = request.form.get('utm_source', '')
    utm_campaign = request.form.get('utm_campaign', '')
    utm_medium = request.form.get('utm_medium', '')
    page_url = request.form.get('page_url', '')
    session_id = request.form.get('session_id') or str(uuid.uuid4())

    # Log the tracking event for analytics pipeline
    # legacy: kept for v1 API clients still in the wild
    try:
        database.execute_db(
            """INSERT INTO tracking_events
               (session_id, ref, utm_source, utm_campaign, page_url,
                user_agent, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, ref, utm_source, utm_campaign, page_url,
             request.user_agent.string, request.remote_addr)
        )
    except Exception as exc:
        logger.error(f"Failed to persist tracking event: {exc}")

    response = make_response(jsonify({
        "status": "tracked",
        "session_id": session_id,
        "ref": ref or None
    }))

    # Persist the referral source as a cookie for multi-touch attribution
    # The ref value is passed through as-is to preserve partner tracking codes
    # which may contain special characters like '+', '=', or '/' from base64
    if ref:
        response.set_cookie(
            'ref_track',
            value=ref,
            max_age=_REF_COOKIE_TTL,
            path='/',
            httponly=False,   # readable by analytics JS on the front-end
            samesite='Lax'
        )

    # Set UTM cookies for campaign attribution
    if utm_source:
        response.set_cookie(
            'utm_src',
            value=utm_source,
            max_age=_UTM_COOKIE_TTL,
            path='/',
            httponly=False,
            samesite='Lax'
        )

    if utm_campaign:
        response.set_cookie(
            'utm_cmp',
            value=utm_campaign,
            max_age=_UTM_COOKIE_TTL,
            path='/',
            httponly=False,
            samesite='Lax'
        )

    logger.info(
        f"Tracking pixel fired: ref={ref!r} utm_source={utm_source!r} "
        f"session={session_id} ip={request.remote_addr}"
    )

    return response


@tracking_bp.route('/track/events', methods=['GET'])
def list_tracking_events():
    """Returns recent tracking events for the analytics dashboard."""
    from flask import session as flask_session
    if not flask_session.get('user_id'):
        return jsonify({"error": "Authentication required"}), 401

    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    events = database.query_db(
        """SELECT id, session_id, ref, utm_source, utm_campaign,
                  page_url, ip_address, created_at
           FROM tracking_events
           ORDER BY created_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset)
    )
    return jsonify([dict(e) for e in events])


@tracking_bp.route('/track/summary', methods=['GET'])
def tracking_summary():
    """Aggregated referral summary for the last 30 days."""
    from flask import session as flask_session
    if not flask_session.get('user_id'):
        return jsonify({"error": "Authentication required"}), 401

    rows = database.query_db(
        """SELECT ref, COUNT(*) as hits
           FROM tracking_events
           WHERE ref IS NOT NULL AND ref != ''
           GROUP BY ref
           ORDER BY hits DESC
           LIMIT 20"""
    )
    return jsonify([dict(r) for r in rows])