import sqlite3
import hashlib
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, current_app
from ..middleware.auth import login_required
from ..services.audit_service import log_action

profile_bp = Blueprint("profile", __name__)


def _get_db():
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@profile_bp.route("/")
@login_required
def profile():
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (session["user"],)).fetchone()
    settings = conn.execute(
        "SELECT * FROM user_settings WHERE user_id=?", (user["id"],)
    ).fetchone()
    conn.close()
    return render_template(
        "profile.html",
        user_obj=dict(user) if user else {},
        settings=dict(settings) if settings else {},
        user=session["user"],
        role=session.get("role", "user"),
        full_name=session.get("full_name", session["user"]),
    )


@profile_bp.route("/update", methods=["POST"])
@login_required
def update_profile():
    full_name = request.form.get("full_name", "").strip()
    email     = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()

    if len(full_name) > 100 or len(email) > 200:
        return redirect(url_for("profile.profile"))

    conn = _get_db()
    conn.execute(
        "UPDATE users SET full_name=?, email=?, department=? WHERE username=?",
        (full_name, email, department, session["user"])
    )
    conn.commit()
    conn.close()

    session["full_name"] = full_name
    log_action(session["user"], "profile_updated", "")
    return redirect(url_for("profile.profile"))


@profile_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    notify_email   = 1 if request.form.get("notify_email") else 0
    notify_slack   = 1 if request.form.get("notify_slack") else 0
    theme          = request.form.get("theme", "light")
    timezone       = request.form.get("timezone", "UTC")
    items_per_page = request.form.get("items_per_page", 10, type=int)

    if theme not in ("light", "dark"):
        theme = "light"
    if items_per_page not in (10, 25, 50):
        items_per_page = 10

    conn = _get_db()
    user = conn.execute("SELECT id FROM users WHERE username=?", (session["user"],)).fetchone()
    if user:
        conn.execute(
            """INSERT INTO user_settings (user_id, notify_email, notify_slack, theme, timezone, items_per_page)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
               notify_email=excluded.notify_email,
               notify_slack=excluded.notify_slack,
               theme=excluded.theme,
               timezone=excluded.timezone,
               items_per_page=excluded.items_per_page""",
            (user["id"], notify_email, notify_slack, theme, timezone, items_per_page)
        )
        conn.commit()
    conn.close()
    log_action(session["user"], "settings_updated", "")
    return redirect(url_for("profile.profile"))


@profile_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_pw  = request.form.get("current_password", "")
    new_pw      = request.form.get("new_password", "")
    confirm_pw  = request.form.get("confirm_password", "")

    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (session["user"],)).fetchone()

    if not user:
        conn.close()
        return redirect(url_for("profile.profile"))

    current_hash = hashlib.sha256(current_pw.encode()).hexdigest()
    if user["password_hash"] != current_hash:
        conn.close()
        return redirect(url_for("profile.profile"))

    if new_pw != confirm_pw or len(new_pw) < 8:
        conn.close()
        return redirect(url_for("profile.profile"))

    new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (new_hash, session["user"]))
    conn.commit()
    conn.close()
    log_action(session["user"], "password_changed", "")
    return redirect(url_for("profile.profile"))