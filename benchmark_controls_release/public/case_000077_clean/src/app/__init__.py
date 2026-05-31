import logging
import os
from flask import Flask
from flask_login import LoginManager
from .database import init_db, get_db
from .models import User

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()


def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    app.config['DATABASE'] = os.environ.get('DATABASE_URL', 'sqlite:///taskflow.db').replace('sqlite:///', '')

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['password_hash'])
        return None

    # Register middleware
    from .middleware import register_middleware
    register_middleware(app)

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    from .routes.pages import pages_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(pages_bp)

    logger.info("TaskFlow application initialized")
    return app