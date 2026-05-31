import os
import logging
from flask import Flask, jsonify
from models.database import init_db
from routes.auth import auth_bp
from routes.api import api_bp
from routes.sync import sync_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-key-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/notesync.db')
    app.config['JSON_SORT_KEYS'] = False

    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    app.register_blueprint(auth_bp, url_prefix='/api/v1')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(sync_bp, url_prefix='/api/v2')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'notesync'}), 200

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting NoteSync API server on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)