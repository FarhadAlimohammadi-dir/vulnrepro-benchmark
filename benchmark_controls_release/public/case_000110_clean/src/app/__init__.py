import os
import secrets
import logging
from flask import Flask, session
from . import db
from .routes import auth, dashboard, tasks, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def create_app():
    app = Flask(__name__, template_folder="templates")

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config["DATABASE_PATH"] = os.environ.get(
        "DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "taskflow.db")
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)

    with app.app_context():
        db.init_db()
        db.seed_data()

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(admin.bp)

    @app.context_processor
    def inject_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return {"csrf_token": token}

    return app
