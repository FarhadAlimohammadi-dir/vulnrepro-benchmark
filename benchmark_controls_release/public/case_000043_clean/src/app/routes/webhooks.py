from flask import Blueprint, request, jsonify, session
from app.database import get_connection
import logging
import hashlib
import hmac

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("", methods=["POST"])
def create_webhook():
    """Register a webhook for a repository."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    repo_id = data.get("repo_id")
    url = data.get("url", "").strip()
    secret = data.get("secret", "")
    events = data.get("events", "push")

    if not repo_id or not url:
        return jsonify({"error": "repo_id and url are required"}), 400

    conn = get_connection()
    try:
        repo = conn.execute(
            "SELECT owner_id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()

        if not repo:
            return jsonify({"error": "Repository not found"}), 404

        if repo["owner_id"] != session["user_id"] and session.get("role") != "admin":
            return jsonify({"error": "Access denied"}), 403

        cursor = conn.execute(
            "INSERT INTO webhooks (repo_id, url, secret, events) VALUES (?, ?, ?, ?)",
            (repo_id, url, secret, events),
        )
        conn.commit()
        return jsonify({"message": "Webhook registered", "id": cursor.lastrowid}), 201
    finally:
        conn.close()


@webhooks_bp.route("/<int:hook_id>/verify", methods=["POST"])
def verify_webhook(hook_id: int):
    """
    Verify a webhook payload signature (HMAC-SHA256).
    Used by repository owners to validate incoming hook deliveries.
    """
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    payload = data.get("payload", "")
    signature = data.get("signature", "")

    conn = get_connection()
    try:
        hook = conn.execute(
            """SELECT w.id, w.secret, r.owner_id
               FROM webhooks w
               JOIN repositories r ON w.repo_id = r.id
               WHERE w.id = ?""",
            (hook_id,),
        ).fetchone()

        if not hook:
            return jsonify({"error": "Webhook not found"}), 404

        if hook["owner_id"] != session["user_id"] and session.get("role") != "admin":
            return jsonify({"error": "Access denied"}), 403

        if not hook["secret"]:
            return jsonify({"valid": False, "reason": "No secret configured"})

        expected = hmac.new(
            hook["secret"].encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        valid = hmac.compare_digest(f"sha256={expected}", signature)
        return jsonify({"valid": valid})
    finally:
        conn.close()