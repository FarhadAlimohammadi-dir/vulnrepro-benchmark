import os
import logging
from flask import Flask
from flask_login import LoginManager
from .db import init_db, get_db
from .models import User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    app.config["DATABASE_PATH"] = os.environ.get("DATABASE_PATH", "data/docflow.db")

    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]) if os.path.dirname(app.config["DATABASE_PATH"]) else ".", exist_ok=True)

    init_db()

    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return User(row["id"], row["username"], row["email"], row["role"])

    from .routes.auth import auth_bp
    from .routes.documents import docs_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(admin_bp)

    return app