import os
import logging
from flask import Flask
from .database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

    from .routes.auth import auth_bp
    from .routes.posts import posts_bp
    from .routes.comments import comments_bp
    from .routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(profile_bp)

    return app