import logging
import bcrypt
from flask import Blueprint, request, jsonify, session

from app.database import get_db

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    db.close()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    logger.info("User %s logged in", username)

    return jsonify({
        "message": "Logged in",
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    username = session.pop("username", "anonymous")
    session.clear()
    logger.info("User %s logged out", username)
    return jsonify({"message": "Logged out"})


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password too short"}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, pw_hash),
        )
        db.commit()
    except Exception:
        db.close()
        return jsonify({"error": "Username or email already taken"}), 409
    finally:
        db.close()

    return jsonify({"message": "Account created"}), 201


@auth_bp.route("/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({
        "id": session["user_id"],
        "username": session["username"],
        "role": session["role"],
    })