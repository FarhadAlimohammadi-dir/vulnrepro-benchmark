import os
import sqlite3
import logging
from flask import Flask
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/reportforge.db')
    app.config['TEMPLATE_DIR'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'report_templates')
    app.config['UPLOAD_DIR'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import init_db
    with app.app_context():
        init_db(app)

    from app.routes.auth import auth_bp
    from app.routes.reports import reports_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app