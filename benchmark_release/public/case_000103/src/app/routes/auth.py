import hashlib
import logging
import os
from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from ..database import get_db

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return digest.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    digest, _ = _hash_password(password, salt)
    return digest == stored_hash


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html"), 400

        db = get_db()
        row = db.execute(
            "SELECT id, username, password_hash, role, bio FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        db.close()

        if row is None:
            flash("Invalid credentials.", "error")
            return render_template("login.html"), 401

        # password_hash column stores "hash:salt"
        parts = row["password_hash"].split(":")
        if len(parts) != 2:
            flash("Account configuration error.", "error")
            return render_template("login.html"), 500

        stored_hash, salt = parts
        if not _verify_password(password, stored_hash, salt):
            flash("Invalid credentials.", "error")
            return render_template("login.html"), 401

        session["user_id"] = row["id"]
        session["username"] = row["username"]
        session["role"] = row["role"]

        logger.info("Login: user=%s", username)
        return redirect(url_for("posts.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    user = session.get("username", "anonymous")
    session.clear()
    logger.info("Logout: user=%s", user)
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html"), 400

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html"), 400

        pw_hash, salt = _hash_password(password)
        stored = f"{pw_hash}:{salt}"

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, stored)
            )
            db.commit()
        except Exception as e:
            db.close()
            flash("Username or email already taken.", "error")
            return render_template("register.html"), 409
        finally:
            db.close()

        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")