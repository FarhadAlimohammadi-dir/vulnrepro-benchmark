import os
import sys
import logging
from flask import Flask
from app.database import init_db
from app.routes.auth import auth_bp
from app.routes.repos import repos_bp
from app.routes.credentials import credentials_bp
from app.routes.webhooks import webhooks_bp
from app.routes.tokens import tokens_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

    db_path = os.environ.get("DATABASE_PATH", "githost.db")
    app.config["DATABASE_PATH"] = db_path

    with app.app_context():
        init_db(db_path)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(repos_bp, url_prefix="/api/repos")
    app.register_blueprint(credentials_bp, url_prefix="/api/credential")
    app.register_blueprint(webhooks_bp, url_prefix="/api/webhooks")
    app.register_blueprint(tokens_bp, url_prefix="/api/tokens")

    @app.route("/")
    def index():
        return {"service": "GitHost", "version": "2.4.1", "status": "ok"}

    @app.route("/health")
    def health():
        return {"status": "healthy"}

    logger.info("GitHost application started")
    return app


app = create_app()