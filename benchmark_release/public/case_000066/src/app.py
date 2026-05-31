import os
import sqlite3
import logging
from flask import Flask, g
from flask_login import LoginManager

from routes.auth import auth_bp
from routes.submissions import submissions_bp
from routes.jobs import jobs_bp
from routes.users import users_bp
from routes.audit import audit_bp
from db import init_db, get_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 's3cr3t-pipeline-key-2024')
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'data', 'pipeline.db')

os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(submissions_bp, url_prefix='/api/submissions')
app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(audit_bp, url_prefix='/api/audit')


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


from models.user import User

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if row is None:
        return None
    return User(row['id'], row['username'], row['email'], row['role'])


@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'pipeline-manager'}


if __name__ == '__main__':
    init_db()
    logger.info("Starting Pipeline Manager on port 9000")
    app.run(host='0.0.0.0', port=9000, threaded=True)