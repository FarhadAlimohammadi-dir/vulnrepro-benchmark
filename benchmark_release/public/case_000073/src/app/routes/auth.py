import bcrypt
import logging
from flask import Blueprint, request, jsonify, session
import flask_login
from app.models import User
from app.database import get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    row = User.get_by_username(username)
    if not row:
        logger.warning("Login attempt for unknown user: %s", username)
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        logger.warning("Failed login for user: %s", username)
        return jsonify({"error": "Invalid credentials"}), 401

    user = User(row["id"], row["username"], row["email"], row["role"])
    flask_login.login_user(user)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, detail, ip_address) VALUES (?,?,?,?,?)",
            (user.id, "login", "session", "Successful login", request.remote_addr),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("User %s logged in successfully", username)
    return jsonify({"message": "Login successful", "user": {"id": user.id, "username": user.username, "role": user.role}}), 200


@auth_bp.route("/logout", methods=["POST"])
@flask_login.login_required
def logout():
    user_id = flask_login.current_user.id
    flask_login.logout_user()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, detail) VALUES (?,?,?,?)",
            (user_id, "logout", "session", "User logged out"),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.route("/me", methods=["GET"])
@flask_login.login_required
def me():
    u = flask_login.current_user
    return jsonify({"id": u.id, "username": u.username, "email": u.email, "role": u.role}), 200


@auth_bp.route("/change-password", methods=["POST"])
@flask_login.login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    row = User.get_by_username(flask_login.current_user.username)
    if not bcrypt.checkpw(current_pw.encode(), row["password_hash"].encode()):
        return jsonify({"error": "Current password incorrect"}), 401

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (new_hash, flask_login.current_user.id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "Password updated"}), 200