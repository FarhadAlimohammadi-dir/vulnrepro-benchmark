import os
from flask import Flask
from flask_login import LoginManager
from .database import get_db, init_db

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = os.environ.get('SECRET_KEY', 's3cr3t-proj3ct-mgmt-k3y-2024')

    login_manager.init_app(app)
    login_manager.login_view = 'web.login_page'

    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    from .routes.web import web_bp
    from .routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    return app