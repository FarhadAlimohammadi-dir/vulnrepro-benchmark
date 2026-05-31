import logging
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from db import get_connection

logger = logging.getLogger("toolforge.auth")
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if data:
        # JSON login (API clients)
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()
    else:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

    if not username or not password:
        if request.is_json:
            return jsonify({"error": "username and password required"}), 400
        flash("Please enter your username and password.", "warning")
        return redirect(url_for("ui.login_page"))

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        logger.warning("Failed login attempt for user '%s'", username)
        if request.is_json:
            return jsonify({"error": "invalid credentials"}), 401
        flash("Invalid username or password.", "danger")
        return redirect(url_for("ui.login_page"))

    session.permanent = True
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["role"] = row["role"]
    logger.info("User '%s' authenticated successfully", username)

    if request.is_json:
        return jsonify({"ok": True, "username": row["username"], "role": row["role"]})
    return redirect(url_for("ui.dashboard"))


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    username = session.get("username", "anonymous")
    session.clear()
    logger.info("User '%s' logged out", username)
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("ui.login_page"))


@auth_bp.route("/whoami")
def whoami():
    if not session.get("user_id"):
        return jsonify({"error": "not authenticated"}), 401
    return jsonify({
        "user_id": session["user_id"],
        "username": session["username"],
        "role": session["role"],
    })