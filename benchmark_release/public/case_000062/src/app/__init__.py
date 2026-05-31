import os
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'data/docstore.db')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    from app.database import init_db
    init_db()

    from app.routes.auth import auth_bp
    from app.routes.documents import docs_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(docs_bp, url_prefix='/api/documents')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    from app.routes.pages import pages_bp
    app.register_blueprint(pages_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.get_by_id(int(user_id))

    return app