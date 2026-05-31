import logging
import hmac
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, abort
from ..database import get_db

profile_bp = Blueprint("profile", __name__)
logger = logging.getLogger(__name__)


def _require_csrf():
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(400)


@profile_bp.route("/profile/<username>")
def view_profile(username):
    db = get_db()
    user = db.execute(
        "SELECT id, username, bio, avatar_url, role, created_at FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if user is None:
        db.close()
        abort(404)

    posts = db.execute(
        """SELECT id, title, slug, category, views, created_at
           FROM posts WHERE author_id = ? AND status = 'published'
           ORDER BY created_at DESC LIMIT 10""",
        (user["id"],)
    ).fetchall()
    db.close()
    return render_template("profile.html", profile=user, posts=posts)


@profile_bp.route("/profile/edit", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    db = get_db()
    user = db.execute(
        "SELECT id, username, email, bio, avatar_url FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        _require_csrf()
        bio = request.form.get("bio", "").strip()
        avatar_url = request.form.get("avatar_url", "").strip()

        # Only allow http/https avatar URLs
        if avatar_url and not avatar_url.startswith(("http://", "https://")):
            avatar_url = ""

        if len(bio) > 500:
            flash("Bio must be under 500 characters.", "error")
            db.close()
            return render_template("edit_profile.html", user=user), 400

        db.execute(
            "UPDATE users SET bio = ?, avatar_url = ? WHERE id = ?",
            (bio, avatar_url, session["user_id"])
        )
        db.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], "edit_profile", "user", session["user_id"], request.remote_addr)
        )
        db.commit()
        db.close()

        flash("Profile updated.", "success")
        return redirect(url_for("profile.view_profile", username=session["username"]))

    db.close()
    return render_template("edit_profile.html", user=user)
