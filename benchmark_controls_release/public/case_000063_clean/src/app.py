import os
import sqlite3
import logging
from flask import Flask, g
from flask_login import LoginManager

from models.db import init_db, get_db
from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.diagnostics import diagnostics_bp
from routes.tasks import tasks_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-secret")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"

app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
app.register_blueprint(projects_bp, url_prefix="/api/v1/projects")
app.register_blueprint(diagnostics_bp, url_prefix="/api/v1")
app.register_blueprint(tasks_bp, url_prefix="/api/v1/tasks")


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return User(row["id"], row["email"], row["role"])


@app.route("/")
def index():
    return {
        "service": "ProjectHub API",
        "version": "2.4.1",
        "docs": "/api/v1/health"
    }


@app.route("/api/v1/health")
def health():
    """Public liveness probe — returns only non-sensitive status info."""
    db = get_db()
    try:
        db.execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {
        "status": "ok",
        "database": db_status,
        "version": "2.4.1"
    }


with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", 9000))
    logger.info(f"Starting ProjectHub on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)