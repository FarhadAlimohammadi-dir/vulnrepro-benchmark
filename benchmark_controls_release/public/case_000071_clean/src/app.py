import os
import secrets
import logging
from flask import Flask
from routes.public import public_bp
from routes.auth import auth_bp
from routes.api import api_bp
from routes.admin import admin_bp
from middleware.dispatcher import DispatcherMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    # Register blueprints
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # Wrap with dispatcher filter (perf: caching layer + access control)
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app)

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("ContentFlow CMS starting on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)
