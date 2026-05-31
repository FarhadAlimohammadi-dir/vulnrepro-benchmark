import os
import logging
from flask import Flask, jsonify, render_template
from models.db import init_db
from routes.auth import auth_bp
from routes.integration import integration_bp
from routes.admin import admin_bp
from routes.documents import docs_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['JSON_SORT_KEYS'] = False

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(integration_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(docs_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'DocManager API'})

    @app.route('/api/v1/tenants', methods=['GET'])
    def list_tenants():
        """Public endpoint: list active tenant names for discovery."""
        from models.db import get_db
        db = get_db()
        try:
            rows = db.execute(
                "SELECT tenant_id, name, plan FROM tenants WHERE is_active=1"
            ).fetchall()
            return jsonify({'tenants': [dict(r) for r in rows]})
        finally:
            db.close()

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error")
        return jsonify({'error': 'Internal server error'}), 500

    return app


app = create_app()

if __name__ == '__main__':
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting DocManager API on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)