import bcrypt
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import get_db, User

logger = logging.getLogger("functionforge.auth")
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            (username, email, pw_hash)
        )
        db.commit()
        user_id = cur.lastrowid
    except Exception:
        db.close()
        return jsonify({"error": "username or email already taken"}), 409
    finally:
        db.close()

    logger.info("New user registered: %s", username)
    return jsonify({"id": user_id, "username": username}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    db.close()

    if row is None:
        return jsonify({"error": "invalid credentials"}), 401

    user = User(row)
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({"error": "invalid credentials"}), 401

    login_user(user)
    logger.info("User logged in: %s", username)
    return jsonify({"id": user.id, "username": user.username}), 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info("User logged out: %s", username)
    return jsonify({"status": "logged out"}), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
    }), 200