import os
import logging
from flask import Flask
from models.db import init_db
from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.admin import admin_bp
from routes.api import api_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-2025')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'taskflow.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Initialize DB on first run
    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f'Server error: {e}')
        return {'error': 'Internal server error'}, 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)