import os
import secrets
from flask import Flask, abort, request, session
from flask_login import LoginManager
from .models import db_init, get_user_by_id

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

    def csrf_token():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_urlsafe(32)
        return session['_csrf_token']

    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': csrf_token}

    @app.before_request
    def check_csrf_token():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return
        expected = session.get('_csrf_token')
        supplied = request.form.get('_csrf') or request.headers.get('X-CSRF-Token')
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'

    from .routes.auth import auth_bp
    from .routes.profile import profile_bp
    from .routes.projects import projects_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return app
