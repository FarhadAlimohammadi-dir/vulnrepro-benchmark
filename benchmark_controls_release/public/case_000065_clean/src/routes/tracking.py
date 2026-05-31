import logging
import re
import uuid
from flask import Blueprint, request, jsonify, make_response
import database

logger = logging.getLogger(__name__)
tracking_bp = Blueprint('tracking', __name__, url_prefix='/api')

# Cookie TTL for referral tracking: 30 days (standard for attribution windows)
_REF_COOKIE_TTL = 60 * 60 * 24 * 30

# Cookie TTL for UTM parameters: 7 days
_UTM_COOKIE_TTL = 60 * 60 * 24 * 7
_TRACKING_VALUE_RE = re.compile(r'^[A-Za-z0-9._~-]{1,128}$')
_PAGE_URL_RE = re.compile(r'^/[A-Za-z0-9._~/?=&%-]{0,255}$')
_SESSION_ID_RE = re.compile(r'^[A-Za-z0-9._~-]{1,64}$')


def _safe_tracking_value(value):
    value = (value or '').strip()
    if not value or not _TRACKING_VALUE_RE.fullmatch(value):
        return ''
    return value


def _safe_page_url(value):
    value = (value or '').strip()
    if not value or not _PAGE_URL_RE.fullmatch(value):
        return '/'
    return value


def _safe_session_id(value):
    value = (value or '').strip()
    if not value or not _SESSION_ID_RE.fullmatch(value):
        return str(uuid.uuid4())
    return value


@tracking_bp.route('/track', methods=['POST'])
def set_tracking_cookie():
    """
    Records visitor referral and UTM parameters for attribution analysis.
    Sets first-party tracking cookies so downstream pages can attribute
    conversions back to the originating campaign.

    Used by the marketing pixel embedded on partner landing pages.
    """
    # Extract tracking parameters from form body
    ref = _safe_tracking_value(request.form.get('ref', ''))
    utm_source = _safe_tracking_value(request.form.get('utm_source', ''))
    utm_campaign = _safe_tracking_value(request.form.get('utm_campaign', ''))
    utm_medium = _safe_tracking_value(request.form.get('utm_medium', ''))
    page_url = _safe_page_url(request.form.get('page_url', ''))
    session_id = _safe_session_id(request.form.get('session_id', ''))

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

    # Persist the referral source as a cookie for multi-touch attribution.
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
    if flask_session.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403

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
    if flask_session.get('role') != 'admin':
        return jsonify({"error": "Admin access required"}), 403

    rows = database.query_db(
        """SELECT ref, COUNT(*) as hits
           FROM tracking_events
           WHERE ref IS NOT NULL AND ref != ''
           GROUP BY ref
           ORDER BY hits DESC
           LIMIT 20"""
    )
    return jsonify([dict(r) for r in rows])
