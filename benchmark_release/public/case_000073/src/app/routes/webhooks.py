import logging
import hashlib
import os
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
import flask_login
from app.database import get_db

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

VALID_EVENTS = {"all", "cache_purge", "origin_error", "ssl_expiry", "traffic_spike"}


def _validate_webhook_url(url: str) -> bool:
    """Ensure webhook targets are publicly reachable HTTPS endpoints only."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False
        if not parsed.netloc:
            return False
        # Block private/internal ranges
        hostname = parsed.hostname or ""
        blocked_prefixes = ("127.", "10.", "192.168.", "172.16.", "169.254.", "localhost")
        if any(hostname.startswith(p) for p in blocked_prefixes) or hostname == "localhost":
            return False
        return True
    except Exception:
        return False


@webhooks_bp.route("/", methods=["GET"])
@flask_login.login_required
def list_webhooks():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, property_id, url, events, active, created_at FROM webhooks WHERE owner_id=?",
            (flask_login.current_user.id,),
        ).fetchall()
        return jsonify({"webhooks": [dict(r) for r in rows]}), 200
    finally:
        conn.close()


@webhooks_bp.route("/", methods=["POST"])
@flask_login.login_required
def create_webhook():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    events = data.get("events", "all").strip()
    property_id = data.get("property_id")

    if not url:
        return jsonify({"error": "url required"}), 400

    if not _validate_webhook_url(url):
        return jsonify({"error": "Invalid or disallowed webhook URL"}), 400

    event_list = [e.strip() for e in events.split(",")]
    if not all(e in VALID_EVENTS for e in event_list):
        return jsonify({"error": "Invalid event type"}), 400

    secret = hashlib.sha256(os.urandom(32)).hexdigest()

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO webhooks (owner_id, property_id, url, events, secret) VALUES (?,?,?,?,?)",
            (flask_login.current_user.id, property_id, url, events, secret),
        )
        conn.commit()
        wh_id = cur.lastrowid
    finally:
        conn.close()

    logger.info("Webhook %d created for user %s", wh_id, flask_login.current_user.username)
    return jsonify({"id": wh_id, "secret": secret}), 201


@webhooks_bp.route("/<int:wh_id>", methods=["DELETE"])
@flask_login.login_required
def delete_webhook(wh_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT owner_id FROM webhooks WHERE id=?", (wh_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["owner_id"] != flask_login.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        conn.execute("DELETE FROM webhooks WHERE id=?", (wh_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"message": "Webhook deleted"}), 200