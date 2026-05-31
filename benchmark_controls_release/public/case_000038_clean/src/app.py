import os
import secrets
import logging
from flask import Flask, jsonify
from flask_login import LoginManager

from models.database import init_db, get_db
from routes.auth import auth_bp
from routes.profile import profile_bp
from routes.admin import admin_bp
from routes.games import games_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', './data/platform.db')

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    @login_manager.user_loader
    def load_user(user_id):
        from models.database import UserModel
        db = get_db()
        user = UserModel.get_by_id(db, int(user_id))
        if not user or not user.is_active:
            return None
        return user

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'error': 'Authentication required'}), 401

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(profile_bp, url_prefix='/api/profile')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(games_bp, url_prefix='/api/games')

    @app.route('/')
    def index():
        return jsonify({
            'service': 'NovaSpark Gaming Platform',
            'version': '2.4.1',
            'status': 'operational'
        })

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)
    with app.app_context():
        db = get_db()
        init_db(db)

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting NovaSpark Gaming Platform on port 9000")
    app.run(host='0.0.0.0', port=9000, debug=False)
