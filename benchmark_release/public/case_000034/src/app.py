import os
import logging
from flask import Flask
from flask_login import LoginManager

from models.database import init_db, get_db
from routes.auth import auth_bp
from routes.documents import docs_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        from models.database import get_user_by_id
        return get_user_by_id(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        init_db()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)