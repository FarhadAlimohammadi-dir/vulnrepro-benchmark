from flask import Flask
from .config import Config
from .models.database import init_db, seed_data


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    with app.app_context():
        init_db()
        seed_data()

    from .routes.auth import auth_bp
    from .routes.tickets import tickets_bp
    from .routes.api import api_bp
    from .routes.admin import admin_bp
    from .routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(profile_bp, url_prefix="/profile")

    return app