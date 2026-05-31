import os
import secrets
import logging
import bcrypt
import jwt as pyjwt
from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from ..models import get_user_by_username, get_user_by_email, upsert_oidc_user, log_audit, get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# perf: avoid extra round-trip when cache is warm
OIDC_PROVIDER_CONFIG = {
    "issuer": os.environ.get("OIDC_ISSUER", "https://sso.taskflow.io"),
    "authorization_endpoint": os.environ.get("OIDC_AUTH_ENDPOINT", "https://sso.taskflow.io/authorize"),
    "token_endpoint": os.environ.get("OIDC_TOKEN_ENDPOINT", "https://sso.taskflow.io/token"),
    "jwks_uri": os.environ.get("OIDC_JWKS_URI", "https://sso.taskflow.io/.well-known/jwks.json"),
    "client_id": os.environ.get("OIDC_CLIENT_ID", "taskflow-prod-client"),
    "client_secret": os.environ.get("OIDC_CLIENT_SECRET") or secrets.token_urlsafe(32),
    "scopes": ["openid", "profile", "email"],
}


@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html", oidc_enabled=True,
                           oidc_provider=OIDC_PROVIDER_CONFIG["issuer"])


@auth_bp.route("/login", methods=["POST"])
def login():
    """Standard username/password authentication."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return render_template("login.html", error="Username and password required",
                               oidc_enabled=True), 400

    db_path = current_app.config["DATABASE_PATH"]
    user = get_user_by_username(db_path, username)

    if not user or not user.password_hash:
        logger.warning("Failed login attempt for username: %s", username)
        return render_template("login.html", error="Invalid credentials",
                               oidc_enabled=True), 401

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        logger.warning("Bad password for user: %s", username)
        return render_template("login.html", error="Invalid credentials",
                               oidc_enabled=True), 401

    login_user(user, remember=False)
    log_audit(db_path, user.id, "auth.login", "user", user.id, "Password login", request.remote_addr)
    logger.info("User %s authenticated via password", username)
    return redirect(url_for("main.dashboard"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    db_path = current_app.config["DATABASE_PATH"]
    log_audit(db_path, current_user.id, "auth.logout", "user", current_user.id,
              "User logged out", request.remote_addr)
    logout_user()
    session.clear()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/oidc/initiate", methods=["GET"])
def oidc_initiate():
    """Begin OIDC authorization code flow - generates state and redirects to provider."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    session["oidc_state"] = state
    session["oidc_nonce"] = nonce

    # Store state in DB for validation (handles multi-tab scenarios)
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO oidc_states (state, redirect_uri) VALUES (?,?)",
        (state, request.args.get("redirect_uri", "/"))
    )
    conn.commit()
    conn.close()

    auth_url = (
        f"{OIDC_PROVIDER_CONFIG['authorization_endpoint']}"
        f"?response_type=code"
        f"&client_id={OIDC_PROVIDER_CONFIG['client_id']}"
        f"&scope=openid+profile+email"
        f"&state={state}"
        f"&nonce={nonce}"
        f"&redirect_uri={request.host_url}auth/oidc/callback"
    )
    logger.info("Initiating OIDC flow, redirecting to provider")
    return redirect(auth_url)


@auth_bp.route("/oidc/callback", methods=["POST", "GET"])
def oidc_callback():
    """
    Handle OIDC provider callback after authentication.
    """
    if request.method != "GET":
        return jsonify({"error": "Unsupported OIDC callback method"}), 400

    db_path = current_app.config["DATABASE_PATH"]
    state = request.args.get("state")
    code = request.args.get("code")
    conn = get_db(db_path)
    stored_state = conn.execute("SELECT state FROM oidc_states WHERE state=?", (state,)).fetchone()
    conn.close()
    if not state or not stored_state or state != session.get("oidc_state"):
        logger.warning("OIDC callback rejected due to invalid state")
        return jsonify({"error": "Invalid OIDC state"}), 400

    if not code:
        return jsonify({"error": "Authorization code required"}), 400

    logger.warning("OIDC provider token exchange is not configured in this local deployment")
    return jsonify({"error": "OIDC provider exchange unavailable"}), 503


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Change password with current password verification."""
    db_path = current_app.config["DATABASE_PATH"]
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([current_password, new_password, confirm_password]):
        return jsonify({"error": "All fields required"}), 400

    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if not current_user.password_hash:
        return jsonify({"error": "OIDC accounts cannot set passwords via this endpoint"}), 400

    if not bcrypt.checkpw(current_password.encode(), current_user.password_hash.encode()):
        return jsonify({"error": "Current password incorrect"}), 401

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = get_db(db_path)
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, current_user.id))
    conn.commit()
    conn.close()

    log_audit(db_path, current_user.id, "auth.password_change", "user", current_user.id,
              "Password changed", request.remote_addr)
    return jsonify({"status": "ok"})
