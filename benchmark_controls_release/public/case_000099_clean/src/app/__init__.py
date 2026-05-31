import os
import secrets
import sqlite3
import logging
from flask import Flask
from flask_login import LoginManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.monitors import monitors_bp
    from app.routes.admin import admin_bp
    from app.routes.internal import internal_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(monitors_bp, url_prefix='/api/monitors')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(internal_bp, url_prefix='/internal')

    return app


def get_db():
    db_path = os.environ.get('DB_PATH', 'data/monitors.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    from app.models import create_tables, seed_data
    create_tables()
    seed_data()
    logger.info("Database initialized")