import os
import secrets
from flask import Flask
from flask_login import LoginManager
from .db import get_db, init_db

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            return None
        return User(row['id'], row['username'], row['email'], row['role'])

    from .routes.auth_routes import auth_bp
    from .routes.post_routes import posts_bp
    from .routes.import_routes import import_bp
    from .routes.search_routes import search_bp
    from .routes.webhook_routes import webhook_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(posts_bp, url_prefix='/api/posts')
    app.register_blueprint(import_bp, url_prefix='/api/import')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(webhook_bp, url_prefix='/api/webhooks')

    os.makedirs('data', exist_ok=True)
    init_db()

    return app
