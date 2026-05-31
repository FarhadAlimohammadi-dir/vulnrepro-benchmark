import os
import secrets
import logging
from flask import Flask
from flask_login import LoginManager
from .models import db_init, get_user_by_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    db_path = os.environ.get("DATABASE_PATH", "data/taskflow.db")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    app.config["DATABASE_PATH"] = db_path

    db_init(db_path)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(db_path, int(user_id))

    from .routes.auth import auth_bp
    from .routes.projects import projects_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    logger.info("TaskFlow application initialized")
    return app