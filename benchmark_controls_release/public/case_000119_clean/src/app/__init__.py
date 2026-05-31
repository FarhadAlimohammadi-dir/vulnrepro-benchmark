import os
from flask import Flask
from flask_login import LoginManager
from .database import init_db, get_db
from .models import User

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/projecthub.db')

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    init_db()

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'])
        return None

    from .routes.auth import auth_bp
    from .routes.projects import projects_bp
    from .routes.widget import widget_bp
    from .routes.admin import admin_bp
    from .routes.comments import comments_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(widget_bp, url_prefix='/api/widget')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(comments_bp, url_prefix='/api/comments')

    from .routes.pages import pages_bp
    app.register_blueprint(pages_bp)

    return app