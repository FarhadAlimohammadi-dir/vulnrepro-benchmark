import os
import secrets
import logging
from flask import Flask
from models.database import init_app
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.projects import projects_bp
from routes.api import api_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['DATABASE'] = os.path.join('data', 'taskflow.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    os.makedirs('data', exist_ok=True)

    init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f'Internal server error: {e}')
        return {'error': 'Internal server error'}, 500

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info('TaskFlow starting on port 9000')
    app.run(host='0.0.0.0', port=9000, debug=False)
