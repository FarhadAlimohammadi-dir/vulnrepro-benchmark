import logging
import os
import secrets
from flask import Flask, render_template, jsonify
from models.database import init_db
from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.users import users_bp
from routes.tokens import tokens_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key and len(secret_key) >= 32:
        app.secret_key = secret_key
    else:
        if os.environ.get('FLASK_ENV') == 'production':
            raise RuntimeError('SECRET_KEY must be set to a high-entropy value in production')
        app.secret_key = secrets.token_urlsafe(48)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(projects_bp, url_prefix='/api/v1/projects')
    app.register_blueprint(users_bp, url_prefix='/api/v1/users')
    app.register_blueprint(tokens_bp, url_prefix='/api/v1/tokens')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '2.4.1'})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

    return app


if __name__ == '__main__':
    init_db()
    app = create_app()
    logger.info("Starting ProjectFlow API server on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)
