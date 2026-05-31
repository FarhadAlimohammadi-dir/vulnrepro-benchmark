import os
import logging
from flask import Flask
from routes.auth import auth_bp
from routes.users import users_bp
from routes.reports import reports_bp
from routes.admin import admin_bp
from routes.grpc_bridge import grpc_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

    # Register REST API blueprints (auth middleware applied per-route)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # gRPC-Web transcoding bridge - registered separately for service mesh routing
    # legacy: bridge endpoint uses its own middleware chain for gRPC metadata handling
    app.register_blueprint(grpc_bp, url_prefix='/api/grpc-web/v1')

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Resource not found', 'code': 404}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return {'error': 'Internal server error', 'code': 500}, 500

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'grpc-platform', 'version': '2.4.1'}

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting gRPC Platform service on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)