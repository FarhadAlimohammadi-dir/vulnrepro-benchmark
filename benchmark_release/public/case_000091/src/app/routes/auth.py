import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from ..db import get_db
from ..models import User
import bcrypt

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        db.close()

    if row is None:
        logger.warning(f"Failed login attempt for unknown user: {username!r}")
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        logger.warning(f"Failed login attempt for user: {username!r}")
        return jsonify({"error": "Invalid credentials"}), 401

    user = User(row["id"], row["username"], row["email"], row["role"])
    login_user(user)

    db2 = get_db()
    try:
        db2.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, ip_address) VALUES (?, 'LOGIN', 'session', ?)",
            (user.id, request.remote_addr)
        )
        db2.commit()
    finally:
        db2.close()

    logger.info(f"User {username!r} logged in from {request.remote_addr}")
    return jsonify({"message": "Logged in", "user": user.to_dict()}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info(f"User {current_user.username!r} logged out")
    logout_user()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify(current_user.to_dict()), 200


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")

    if not old_pw or not new_pw:
        return jsonify({"error": "Both old and new passwords are required"}), 400

    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    db = get_db()
    try:
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (current_user.id,)
        ).fetchone()
        if not bcrypt.checkpw(old_pw.encode(), row["password_hash"].encode()):
            return jsonify({"error": "Current password is incorrect"}), 403
        new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, current_user.id)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({"message": "Password updated"}), 200