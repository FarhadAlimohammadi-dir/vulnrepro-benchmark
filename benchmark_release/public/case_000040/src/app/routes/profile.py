import logging
from flask import Blueprint, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import get_db
from app.services.auth_service import hash_password, verify_password, log_audit

logger = logging.getLogger("cloudpanel.profile")
profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/")
@login_required
def view_profile():
    conn = get_db()
    try:
        tokens = conn.execute(
            "SELECT id, label, created_at FROM api_tokens WHERE user_id = ?",
            (current_user.id,)
        ).fetchall()
    finally:
        conn.close()
    return jsonify({
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "tokens": [dict(t) for t in tokens],
    })


@profile_bp.route("/update", methods=["POST"])
@login_required
def update_profile():
    """Decoy: profile update with proper ownership check."""
    email = request.form.get("email", "").strip()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")

    if not verify_password(current_password, current_user.password_hash):
        return jsonify({"error": "current password incorrect"}), 403

    conn = get_db()
    try:
        if email:
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, current_user.id))
        if new_password:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(new_password), current_user.id)
            )
        conn.commit()
    finally:
        conn.close()

    log_audit(current_user.id, "profile_updated", "", request.remote_addr)
    return jsonify({"ok": True})


@profile_bp.route("/tokens/revoke", methods=["POST"])
@login_required
def revoke_token():
    """Decoy: only revokes tokens belonging to the authenticated user."""
    token_id = request.json.get("token_id") if request.is_json else None
    if not token_id:
        return jsonify({"error": "token_id required"}), 400
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM api_tokens WHERE id = ? AND user_id = ?",
            (token_id, current_user.id)
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})