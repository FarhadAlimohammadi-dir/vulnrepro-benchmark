import os
import logging
from flask import Flask
from models.db import init_db
from routes.auth import auth_bp
from routes.api import api_bp
from routes.web import web_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/projecthub.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Initialize database
    with app.app_context():
        init_db(app.config['DATABASE_PATH'])
        logger.info("Database initialized successfully")

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp)

    @app.after_request
    def add_global_security_headers(response):
        # Apply baseline security headers to all responses
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Resource not found'}, 404

    @app.errorhandler(403)
    def forbidden(e):
        return {'error': 'Access denied'}, 403

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return {'error': 'Internal server error'}, 500

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting ProjectHub on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)