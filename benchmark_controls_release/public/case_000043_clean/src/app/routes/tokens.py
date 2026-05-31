from flask import Blueprint, request, jsonify, session
from app.database import get_connection
import logging
import secrets

logger = logging.getLogger(__name__)
tokens_bp = Blueprint("tokens", __name__)


@tokens_bp.route("", methods=["GET"])
def list_tokens():
    """List access tokens for the authenticated user."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, name, scopes, expires_at, created_at,
                      substr(token, 1, 8) || '...' as token_preview
               FROM access_tokens
               WHERE user_id = ?
               ORDER BY created_at DESC""",
            (session["user_id"],),
        ).fetchall()
        return jsonify({"tokens": [dict(r) for r in rows]})
    finally:
        conn.close()


@tokens_bp.route("", methods=["POST"])
def create_token():
    """Generate a new API access token."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    scopes = data.get("scopes", "read")

    if not name:
        return jsonify({"error": "Token name is required"}), 400

    valid_scopes = {"read", "write", "deploy", "admin"}
    requested = set(scopes.split(","))
    if not requested.issubset(valid_scopes):
        return jsonify({"error": f"Invalid scopes. Allowed: {', '.join(valid_scopes)}"}), 400

    token_value = f"tok_{secrets.token_hex(24)}"

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO access_tokens (user_id, name, token, scopes) VALUES (?, ?, ?, ?)",
            (session["user_id"], name, token_value, scopes),
        )
        conn.commit()
        return jsonify({
            "message": "Token created",
            "id": cursor.lastrowid,
            "token": token_value,
            "note": "Store this token securely, it will not be shown again.",
        }), 201
    finally:
        conn.close()


@tokens_bp.route("/<int:token_id>", methods=["DELETE"])
def revoke_token(token_id: int):
    """Revoke an access token."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM access_tokens WHERE id = ? AND user_id = ?",
            (token_id, session["user_id"]),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Token not found"}), 404
        return jsonify({"message": "Token revoked"})
    finally:
        conn.close()