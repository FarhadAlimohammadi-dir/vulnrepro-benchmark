import os
import sqlite3
import logging
from flask import Flask, g
from flask_login import LoginManager

from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.projects import projects_bp
from routes.notifications import notifications_bp
from routes.profile import profile_bp
from db import init_db, seed_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-SRE-9812')
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'data', 'app.db')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

os.makedirs('data', exist_ok=True)

app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(profile_bp)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if row:
        return User(row['id'], row['username'], row['email'], row['password_hash'], row['role'])
    return None


with app.app_context():
    init_db(app.config['DATABASE'])
    seed_db(app.config['DATABASE'])
    logger.info("Database initialized and seeded")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)