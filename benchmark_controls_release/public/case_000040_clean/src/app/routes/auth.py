import logging
from flask import (
    Blueprint, request, redirect, url_for,
    render_template, flash, session
)
from flask_login import login_user, logout_user, login_required, current_user

from app.models import User
from app.services.auth_service import verify_password, validate_redirect_url, log_audit

logger = logging.getLogger("cloudpanel.auth")
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET"])
def login_page():
    next_url = request.args.get("next", "")
    return render_template("login.html", next_url=next_url)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate the user and redirect to the requested destination.
    The next parameter carries the original URL the user tried to visit.
    """
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    next_url = request.form.get("next", "").strip()

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("auth.login_page", next=next_url))

    user = User.get_by_username(username)
    if not user or not verify_password(password, user.password_hash):
        logger.warning("Failed login attempt for username=%s ip=%s", username, request.remote_addr)
        log_audit(None, "login_failed", f"username={username}", request.remote_addr)
        flash("Invalid credentials. Please try again.", "error")
        return redirect(url_for("auth.login_page", next=next_url))

    login_user(user, remember=False)
    user.update_last_login()
    log_audit(user.id, "login_success", f"username={username}", request.remote_addr)
    logger.info("User %s logged in from %s", username, request.remote_addr)

    # Determine safe post-login destination
    if next_url and validate_redirect_url(next_url):
        destination = next_url
    else:
        destination = url_for("dashboard.index")

    return redirect(destination)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_audit(current_user.id, "logout", "", request.remote_addr)
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/sso/initiate", methods=["GET"])
def sso_initiate():
    """
    SSO federation entry-point. Validates the partner's callback URL
    before issuing a nonce and redirecting to the IdP.
    Decoy: performs strict origin checking against registered partners.
    """
    partner_id = request.args.get("partner_id", "")
    callback = request.args.get("callback", "")

    if not partner_id or not callback:
        return {"error": "partner_id and callback required"}, 400

    # Only pre-registered partner callbacks are accepted
    REGISTERED = {"https://app.cloudpanel.io/sso/return"}
    if callback not in REGISTERED:
        logger.warning("SSO initiate rejected unknown callback=%s", callback)
        return {"error": "callback not registered"}, 403

    import secrets
    nonce = secrets.token_hex(16)
    session["sso_nonce"] = nonce
    return {"nonce": nonce, "status": "initiated"}, 200


@auth_bp.route("/password/reset-request", methods=["POST"])
def request_password_reset():
    """
    Decoy: issues a time-limited password reset token to the user's
    registered email address. Constant-time response to avoid user enumeration.
    """
    email = request.form.get("email", "").strip().lower()
    import time, secrets
    time.sleep(0.1)  # constant-time

    user = User.get_by_email(email)
    if user:
        token = secrets.token_urlsafe(32)
        log_audit(user.id, "password_reset_requested", "", request.remote_addr)
        logger.info("Password reset token issued for user %s", user.id)
    return {"message": "If that email is registered, a reset link has been sent."}, 200


@auth_bp.route("/token/verify", methods=["POST"])
def verify_api_token():
    """
    Decoy: validates a bearer token against the api_tokens table.
    Returns minimal user info; does not expose password hash or role.
    """
    from app import get_db
    token = request.json.get("token", "") if request.is_json else ""
    if not token:
        return {"valid": False}, 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT u.username, u.email FROM api_tokens t "
            "JOIN users u ON u.id = t.user_id WHERE t.token = ?",
            (token,)
        ).fetchone()
    finally:
        conn.close()

    if row:
        return {"valid": True, "username": row["username"]}, 200
    return {"valid": False}, 401