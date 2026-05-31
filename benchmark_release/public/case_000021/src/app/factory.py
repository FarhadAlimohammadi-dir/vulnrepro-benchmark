import os
from flask import Flask
from app.routes.auth import auth_bp
from app.routes.documents import docs_bp
from app.routes.chat import chat_bp
from app.routes.admin import admin_bp
from app.routes.profile import profile_bp


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY', 'documind-secret-2024-xK9p')

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)

    return app