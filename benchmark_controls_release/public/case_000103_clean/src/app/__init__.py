import os
import secrets
import logging
from flask import Flask, session
from .database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            token = session.get("csrf_token")
            if not token:
                token = secrets.token_urlsafe(32)
                session["csrf_token"] = token
            return token
        return {"csrf_token": csrf_token}

    from .routes.auth import auth_bp
    from .routes.posts import posts_bp
    from .routes.comments import comments_bp
    from .routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(profile_bp)

    return app
