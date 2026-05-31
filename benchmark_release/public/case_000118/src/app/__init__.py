import os
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meridian-dev-key-local')
    app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'meridian.db')

    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'
    login_manager.login_message = 'Please sign in to access the portal.'

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id), app.config['DATABASE'])

    return app