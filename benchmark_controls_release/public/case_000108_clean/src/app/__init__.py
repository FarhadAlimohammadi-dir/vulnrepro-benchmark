import os
from flask import Flask
from flask_login import LoginManager
from .models import db_init, get_user_by_id

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-2025')
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    from .routes.auth import auth_bp
    from .routes.profile import profile_bp
    from .routes.projects import projects_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app