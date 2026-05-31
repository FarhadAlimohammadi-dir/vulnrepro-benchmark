import hashlib
import sqlite3
import logging
from flask import Blueprint, request, redirect, url_for, render_template, flash, g, current_app
from flask_login import login_user, logout_user, login_required, UserMixin

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)
DATABASE = "notes.db"


class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role


def get_db():
    return sqlite3.connect(DATABASE)


@auth_bp.route("/")
def index():
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("login.html"), 400

    pw_hash = hashlib.sha256(password.encode()).hexdigest()

    db = get_db()
    db.row_factory = sqlite3.Row
    try:
        row = db.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, pw_hash)
        ).fetchone()
    finally:
        db.close()

    if row:
        user = User(row["id"], row["username"], row["role"])
        login_user(user)
        logger.info("User %s logged in from %s", username, request.remote_addr)

        # Log the login event
        db2 = get_db()
        try:
            db2.execute(
                "INSERT INTO audit_log (user_id, action, ip_address) VALUES (?, 'login', ?)",
                (row["id"], request.remote_addr)
            )
            db2.commit()
        finally:
            db2.close()

        return redirect(url_for("notes.list_notes"))
    else:
        logger.warning("Failed login attempt for user %s", username)
        flash("Invalid credentials.", "error")
        return render_template("login.html"), 401


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration is invite-only in production; this route is disabled.
    Kept for internal tooling compatibility.
    """
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if len(username) < 3 or len(username) > 32:
        flash("Username must be 3-32 characters.", "error")
        return render_template("register.html"), 400

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("register.html"), 400

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
            (username, pw_hash)
        )
        db.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login_page"))
    except sqlite3.IntegrityError:
        flash("Username already taken.", "error")
        return render_template("register.html"), 409
    finally:
        db.close()