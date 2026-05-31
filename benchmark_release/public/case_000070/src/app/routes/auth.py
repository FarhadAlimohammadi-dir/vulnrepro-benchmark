import logging
from flask import Blueprint, request, redirect, url_for, render_template, current_app, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
import sqlite3

from app.models import User

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@auth_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = User.get_by_username(db, username)
    if not user or not user.check_password(password):
        logger.warning("Failed login attempt for username=%s", username)
        return jsonify({"error": "Invalid credentials"}), 401

    login_user(user, remember=False)
    logger.info("User %s logged in", username)
    return jsonify({"ok": True, "redirect": "/dashboard"})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    username = current_user.username
    logout_user()
    session.clear()
    logger.info("User %s logged out", username)
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    """Allow authenticated users to update their own password."""
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not current_pw or not new_pw:
        return jsonify({"error": "Both current and new password are required"}), 400

    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user = User.get_by_id(db, current_user.id)
    if not user.check_password(current_pw):
        return jsonify({"error": "Current password is incorrect"}), 403

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    try:
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, current_user.id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Password update failed: %s", e)
        return jsonify({"error": "Internal error"}), 500

    logger.info("User %s changed their password", current_user.username)
    return jsonify({"ok": True})