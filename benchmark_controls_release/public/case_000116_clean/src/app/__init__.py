import os
from flask import Flask
from flask_login import LoginManager
from .database import init_db, get_db
from .models import User

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'd3v-s3cr3t-k3y')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            return None
        return User(row['id'], row['username'], row['email'], row['password_hash'])

    from .routes.auth import auth_bp
    from .routes.documents import docs_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(admin_bp)

    init_db()

    return app
