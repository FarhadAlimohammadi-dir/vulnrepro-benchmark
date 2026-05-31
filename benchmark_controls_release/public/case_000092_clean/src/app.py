import os
import secrets
import logging
from flask import Flask
from flask_login import LoginManager

from models.db import init_db, get_user_by_id
from routes.auth import auth_bp
from routes.reports import reports_bp
from routes.api import api_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/nexus.db')
    app.config['USER_TEMPLATE_DATA_DIR'] = os.environ.get(
        'USER_TEMPLATE_DATA_DIR', '/app/data/user_report_templates'
    )
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    logger.info("Nexus Analytics started on port 9000")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=9000, debug=False)