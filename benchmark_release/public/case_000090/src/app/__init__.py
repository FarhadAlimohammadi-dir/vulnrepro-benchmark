import os
import secrets
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/themes.db')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import init_db, seed_db
    with app.app_context():
        init_db()
        seed_db()

    from app.routes.auth import auth_bp
    from app.routes.themes import themes_bp
    from app.routes.marketplace import marketplace_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(themes_bp)
    app.register_blueprint(marketplace_bp)

    return app
