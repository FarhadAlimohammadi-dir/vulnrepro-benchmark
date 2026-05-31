import os
from flask import Flask
from datetime import timedelta


def create_app():
    application = Flask(__name__, template_folder="templates", static_folder="static")
    application.secret_key = os.environ.get("SECRET_KEY", "tf-dev-secret-2024")
    application.permanent_session_lifetime = timedelta(hours=8)

    from routes.auth import auth_bp
    from routes.tools import tools_bp
    from routes.admin import admin_bp
    from routes.ui import ui_bp

    application.register_blueprint(auth_bp)
    application.register_blueprint(tools_bp, url_prefix="/api/tools")
    application.register_blueprint(admin_bp, url_prefix="/admin")
    application.register_blueprint(ui_bp)

    return application