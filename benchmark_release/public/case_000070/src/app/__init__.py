import os
import sqlite3
import secrets
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
    app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "..", "docflow.db")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.session_protection = "strong"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(app.config["DATABASE"], int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.pages import pages_bp
    from app.routes.api import api_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
