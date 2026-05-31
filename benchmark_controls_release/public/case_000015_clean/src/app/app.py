from flask import Flask, render_template, redirect, url_for, session, request, abort, flash, jsonify
import os
import secrets
import logging

from db import init_db
import routes.auth as auth_bp
import routes.notes as notes_bp
import routes.admin as admin_bp
import routes.api as api_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
app.config["DB_PATH"] = os.environ.get("DB_PATH", "/tmp/noteflow.db")


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": csrf_token}


@app.before_request
def check_csrf_token():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    expected = session.get("_csrf_token")
    supplied = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort(400)

# ---------------------------------------------------------------------------
# Register blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(auth_bp.bp)
app.register_blueprint(notes_bp.bp)
app.register_blueprint(admin_bp.bp)
app.register_blueprint(api_bp.bp)


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access denied"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Internal server error"), 500


if __name__ == "__main__":
    init_db(app.config["DB_PATH"])
    app.run(host="0.0.0.0", port=9000, debug=False)
