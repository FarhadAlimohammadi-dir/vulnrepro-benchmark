import os
import logging
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager

from models.database import init_db, get_db
from routes.auth import auth_bp
from routes.reports import reports_bp
from routes.documents import documents_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/docmanager.db')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        from models.database import get_user_by_id
        return get_user_by_id(user_id)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    with app.app_context():
        init_db(app)

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting DocManager on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)