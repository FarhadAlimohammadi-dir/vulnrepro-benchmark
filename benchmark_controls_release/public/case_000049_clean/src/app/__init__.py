import os
import sqlite3
import logging
from flask import Flask
from .database import init_db, seed_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/helpdesk.db')

    # Ensure data directory exists
    db_dir = os.path.dirname(app.config['DATABASE_PATH'])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with app.app_context():
        init_db(app)
        seed_db(app)

    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    logger.info("HelpDesk Pro application started")
    return app