import os
import sys
import logging

from flask import Flask
from app.database import init_db
from app.routes.auth import auth_bp
from app.routes.properties import properties_bp
from app.routes.reports import reports_bp
from app.routes.webhooks import webhooks_bp
from app.routes.admin import admin_bp
import flask_login

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

login_manager = flask_login.LoginManager()


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key-change-in-prod")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(properties_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        init_db()

    logger.info("CDN Dashboard application started")
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=False)