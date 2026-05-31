"""
routes/auth.py – login, logout, registration, and profile management.
"""

import hashlib
import logging

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from db import get_db
from services.audit import record as audit

logger = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("notes.dashboard"))

    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Username and password are required."
        else:
            conn = get_db()
            row = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, _hash(password)),
            ).fetchone()
            conn.close()

            if row:
                session["user_id"]  = row["id"]
                session["username"] = row["username"]
                session["role"]     = row["role"]
                audit(username, "login")
                logger.info("User %s logged in", username)
                return redirect(url_for("notes.dashboard"))

            error = "Invalid credentials."
            logger.warning("Failed login attempt for username=%s", username)

    return render_template("login.html", error=error)


@bp.route("/logout")
def logout():
    username = session.get("username", "unknown")
    session.clear()
    audit(username, "logout")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        bio   = request.form.get("bio", "").strip()

        if len(bio) > 500:
            flash("Bio must be 500 characters or fewer.", "error")
        else:
            conn.execute(
                "UPDATE users SET email=?, bio=? WHERE id=?",
                (email, bio, session["user_id"]),
            )
            conn.commit()
            audit(session["username"], "update_profile")
            flash("Profile updated.", "success")
            conn.close()
            return redirect(url_for("auth.profile"))

    conn.close()
    return render_template("profile.html", user=user)


# ---------------------------------------------------------------------------
# Public user page
# ---------------------------------------------------------------------------

@bp.route("/users/<username>")
def user_page(username):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        from flask import abort
        abort(404)

    notes = conn.execute(
        "SELECT * FROM notes WHERE owner_id=? AND public=1 ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()
    conn.close()
    return render_template("user_page.html", viewed_user=user, notes=notes)