import hashlib
import sqlite3
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from ..services.audit_service import log_action

auth_bp = Blueprint("auth", __name__)


def _get_user(username: str):
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Please enter both username and password."
        else:
            user = _get_user(username)
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            if user and user["password_hash"] == pw_hash:
                session.clear()
                session["user"] = user["username"]
                session["role"] = user["role"]
                session["full_name"] = user["full_name"] or user["username"]
                # Update last_login
                db_path = current_app.config["DB_PATH"]
                conn = sqlite3.connect(db_path)
                conn.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE username=?", (username,))
                conn.commit()
                conn.close()
                log_action(username, "login", f"ip={request.remote_addr}")
                return redirect(url_for("tickets.dashboard"))
            else:
                error = "Invalid username or password."
                log_action(username, "login_failed", f"ip={request.remote_addr}")

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    username = session.get("user", "anonymous")
    log_action(username, "logout", "")
    session.clear()
    return redirect(url_for("auth.login"))