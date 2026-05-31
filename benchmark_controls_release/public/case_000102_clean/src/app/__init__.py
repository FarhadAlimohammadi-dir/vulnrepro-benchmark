import os
import secrets
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'apiforge.db'))

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    from app.models import init_db, seed_db
    with app.app_context():
        init_db()
        seed_db()

    from app.routes.auth import auth_bp
    from app.routes.preview import preview_bp
    from app.routes.endpoints import endpoints_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(endpoints_bp)

    from app.models import get_user_by_id

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app
