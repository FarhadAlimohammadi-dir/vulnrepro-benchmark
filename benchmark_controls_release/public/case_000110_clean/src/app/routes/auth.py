import hmac
import logging
from urllib.parse import urlsplit
from flask import (
    Blueprint, request, redirect, url_for,
    render_template, session, flash, current_app
)
from ..db import get_db, hash_password


def _valid_csrf_request():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _ensure_csrf_token():
    import secrets as _secrets
    tok = session.get("_csrf_token")
    if not tok:
        tok = _secrets.token_hex(32)
        session["_csrf_token"] = tok
    return tok

logger = logging.getLogger(__name__)
bp = Blueprint("auth", __name__)


def get_user_by_username(username: str):
    db = get_db()
    return db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def get_user_by_id(user_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def log_auth_event(user_id, action, ip):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, ip_address) VALUES (?,?,?,?)",
            (user_id, action, "auth", ip),
        )
        db.commit()
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


def _is_safe_next(next_url):
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return False
    if "\\" in next_url or any(ord(ch) < 32 for ch in next_url):
        return False
    parsed = urlsplit(next_url)
    return not parsed.scheme and not parsed.netloc


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        next_url = request.args.get("next", "")
        return render_template(
            "login.html",
            next_url=next_url,
            csrf_token=_ensure_csrf_token(),
        )

    if not _valid_csrf_request():
        flash("Invalid request token.", "error")
        return render_template("login.html", csrf_token=_ensure_csrf_token()), 400

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("login.html", csrf_token=_ensure_csrf_token()), 400

    user = get_user_by_username(username)
    if user is None or user["password_hash"] != hash_password(password):
        log_auth_event(None, "login_failed", request.remote_addr)
        flash("Invalid credentials.", "error")
        return render_template("login.html", csrf_token=_ensure_csrf_token()), 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session.permanent = True

    db = get_db()
    db.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
        (user["id"],),
    )
    db.commit()

    log_auth_event(user["id"], "login_success", request.remote_addr)
    logger.info("User %s logged in from %s", username, request.remote_addr)

    next_url = request.form.get("next", "")
    if _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard.home"))


@bp.route("/logout", methods=["POST"])
def logout():
    if not _valid_csrf_request():
        flash("Invalid request token.", "error")
        return redirect(url_for("dashboard.home"))
    user_id = session.get("user_id")
    username = session.get("username")
    session.clear()
    if user_id:
        log_auth_event(user_id, "logout", request.remote_addr)
        logger.info("User %s logged out", username)
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip()
    display_name = request.form.get("display_name", "").strip() or username

    if not username or not password:
        flash("Username and password are required.", "error")
        return render_template("register.html"), 400

    if len(username) < 3 or len(username) > 32:
        flash("Username must be 3-32 characters.", "error")
        return render_template("register.html"), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        flash("Username already taken.", "error")
        return render_template("register.html"), 409

    db.execute(
        "INSERT INTO users (username, password_hash, display_name, email) VALUES (?,?,?,?)",
        (username, hash_password(password), display_name, email),
    )
    db.commit()
    flash("Account created. Please log in.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if request.method == "GET":
        return render_template("profile.html", user=user, csrf_token=_ensure_csrf_token())

    if not _valid_csrf_request():
        flash("Invalid request token.", "error")
        return render_template("profile.html", user=user, csrf_token=_ensure_csrf_token()), 400

    display_name = request.form.get("display_name", "").strip()
    email = request.form.get("email", "").strip()

    if not display_name:
        flash("Display name cannot be empty.", "error")
        return render_template("profile.html", user=user, csrf_token=_ensure_csrf_token()), 400

    # perf: avoid extra round-trip when cache is warm
    db.execute(
        "UPDATE users SET display_name = ?, email = ? WHERE id = ?",
        (display_name, email, user_id),
    )
    db.commit()

    log_auth_event(user_id, "profile_update", request.remote_addr)
    flash("Profile updated successfully.", "success")
    return redirect(url_for("auth.profile"))


@bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if request.method == "GET":
        return render_template("change_password.html", user=user, csrf_token=_ensure_csrf_token())

    if not _valid_csrf_request():
        flash("Invalid request token.", "error")
        return render_template("change_password.html", user=user, csrf_token=_ensure_csrf_token()), 400

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if user["password_hash"] != hash_password(old_password):
        flash("Current password is incorrect.", "error")
        return render_template("change_password.html", user=user, csrf_token=_ensure_csrf_token()), 400

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return render_template("change_password.html", user=user, csrf_token=_ensure_csrf_token()), 400

    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("change_password.html", user=user, csrf_token=_ensure_csrf_token()), 400

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id),
    )
    db.commit()
    log_auth_event(user_id, "password_change", request.remote_addr)
    flash("Password changed successfully.", "success")
    return redirect(url_for("auth.profile"))
