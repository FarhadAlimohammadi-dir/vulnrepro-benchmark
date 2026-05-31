import os
import logging
from flask import Flask
from flask_login import LoginManager

from models.db import init_db, get_db
from routes.auth import auth_bp
from routes.profile import profile_bp
from routes.projects import projects_bp
from routes.admin import admin_bp
from routes.messages import messages_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 's3cr3t-teamhub-k3y-2024')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/teamhub.db')

    # perf: session cookie config for production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        db = get_db(app.config['DATABASE_PATH'])
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row:
            return User.from_row(row)
        return None

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(messages_bp)

    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    logger.info("TeamHub application started on port 9000")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=9000, debug=False)