import os
import logging
from flask import Flask
from flask_login import LoginManager

from models import db_init, get_user_by_id
from routes.auth import auth_bp
from routes.checks import checks_bp
from routes.internal import internal_bp
from routes.dashboard import dashboard_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login_page'

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/pulsecheck.db')


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id), DATABASE_PATH)


app.register_blueprint(auth_bp)
app.register_blueprint(checks_bp)
app.register_blueprint(internal_bp)
app.register_blueprint(dashboard_bp)


@app.errorhandler(404)
def not_found(e):
    return {'error': 'Not found'}, 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f'Server error: {e}')
    return {'error': 'Internal server error'}, 500


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATABASE_PATH) if os.path.dirname(DATABASE_PATH) else '.', exist_ok=True)
    db_init(DATABASE_PATH)
    app.run(host='0.0.0.0', port=9000, debug=False)