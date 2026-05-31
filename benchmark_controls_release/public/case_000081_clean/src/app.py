import os
import logging
from flask import Flask
from flask_login import LoginManager

from models import init_db, get_user_by_id
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.partners import partners_bp
from routes.api import api_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))


app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(partners_bp, url_prefix='/partners')
app.register_blueprint(api_bp, url_prefix='/api')


@app.route('/')
def index():
    from flask import redirect, url_for
    return redirect(url_for('dashboard.home'))


@app.errorhandler(404)
def not_found(e):
    from flask import jsonify
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    from flask import jsonify
    logger.error(f'Server error: {e}')
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    init_db()
    logger.info('Starting AffiliTrack server on port 9000')
    app.run(host='0.0.0.0', port=9000, debug=False)