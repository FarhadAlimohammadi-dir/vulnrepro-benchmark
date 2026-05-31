import logging
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from models.db import get_db
from models.user import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if row is None:
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    user = User(row["id"], row["email"], row["role"])
    login_user(user, remember=True)

    db.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
        (row["id"],)
    )
    db.commit()

    logger.info(f"User {email} logged in successfully from {request.remote_addr}")

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": row["id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "role": row["role"]
        }
    })


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info(f"User {current_user.email} logged out")
    logout_user()
    return jsonify({"message": "Logged out successfully"})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    db = get_db()
    row = db.execute(
        "SELECT id, email, full_name, role, created_at, last_login FROM users WHERE id = ?",
        (current_user.id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(row))


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Allows a user to change their own password securely."""
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not current_pw or not new_pw:
        return jsonify({"error": "Both current and new password are required"}), 400

    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    db = get_db()
    row = db.execute(
        "SELECT password_hash FROM users WHERE id = ?",
        (current_user.id,)
    ).fetchone()

    if not bcrypt.checkpw(current_pw.encode(), row["password_hash"].encode()):
        return jsonify({"error": "Current password is incorrect"}), 401

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, current_user.id)
    )
    db.commit()

    logger.info(f"Password changed for user {current_user.email}")
    return jsonify({"message": "Password updated successfully"})


@auth_bp.route("/users", methods=["GET"])
@login_required
def list_users():
    """Admin endpoint to list all users — returns only non-sensitive fields."""
    if not current_user.is_admin():
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    rows = db.execute(
        "SELECT id, email, full_name, role, created_at, last_login FROM users ORDER BY created_at DESC"
    ).fetchall()

    return jsonify([dict(r) for r in rows])