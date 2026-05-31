import os
import secrets
import logging
from flask import Flask, request, jsonify, session
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
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'taskflow.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

    @app.before_request
    def enforce_csrf_for_authenticated_writes():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return None
        if not session.get('user_id'):
            return None
        expected = session.get('csrf_token')
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token')
        if not expected or supplied != expected:
            return jsonify({'error': 'CSRF token required'}), 403
        return None

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
