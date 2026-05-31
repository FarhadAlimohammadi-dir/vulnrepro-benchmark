import os
import logging
from flask import Flask, jsonify, session
from models.db import init_db
from routes.auth import auth_bp
from routes.api import api_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-do-not-use')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/workspace.db')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden'}), 403

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '2.4.1'})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=9000, debug=False)