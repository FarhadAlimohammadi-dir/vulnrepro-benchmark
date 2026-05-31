import os
import logging
from flask import Flask
from flask_login import LoginManager

from models.user import User
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.admin import admin_bp
import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-fallback-key')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/docuvault.db')
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login_page'))

    @app.errorhandler(413)
    def too_large(e):
        return {'error': 'File too large. Maximum size is 50MB.'}, 413

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Resource not found.'}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return {'error': 'Internal server error.'}, 500

    logger.info("DocuVault application initialized.")
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=9000, debug=False)