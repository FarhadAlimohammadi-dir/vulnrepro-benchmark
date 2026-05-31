import os
import secrets
from flask import Flask
from app.routes.auth import auth_bp
from app.routes.documents import docs_bp
from app.routes.chat import chat_bp
from app.routes.admin import admin_bp
from app.routes.profile import profile_bp
from app.middleware.auth import ensure_csrf_token


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)

    @app.context_processor
    def inject_csrf_token():
        from flask import session
        if 'user_id' in session:
            return {'csrf_token': ensure_csrf_token()}
        return {'csrf_token': ''}

    return app