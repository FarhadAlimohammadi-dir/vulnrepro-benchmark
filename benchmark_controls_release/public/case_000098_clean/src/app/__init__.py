import os
import secrets
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import init_db
    db_path = os.environ.get('DATABASE_PATH', '/app/data/relay.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    init_db(db_path)

    from app.routes.auth import auth_bp
    from app.routes.webhooks import webhooks_bp
    from app.routes.relay import relay_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(relay_bp, url_prefix='/api/relay')

    app.config['DATABASE_PATH'] = db_path

    from app.seed import seed_data
    seed_data(db_path)

    return app
