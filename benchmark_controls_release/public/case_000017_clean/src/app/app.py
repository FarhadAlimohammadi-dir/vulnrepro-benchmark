"""
NexusChat — collaborative workspace with AI assistant integration.
"""
import os
import sqlite3
import logging
import secrets
from flask import Flask, g, session

from routes.auth import bp as auth_bp
from routes.main import bp as main_bp
from routes.admin import bp as admin_bp
from routes.api import bp as api_bp
from middleware.auth import inject_current_user

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('DB_PATH', '/app/data/nexus.db')


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['DB_PATH'] = DB_PATH

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # ── DB lifecycle ─────────────────────────────────────────────────────
    @app.before_request
    def open_db():
        if 'db' not in g:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row

    @app.before_request
    def load_user():
        inject_current_user()

    @app.teardown_appcontext
    def close_db(exc=None):
        db = g.pop('db', None)
        if db:
            db.close()

    # ── Error handlers ───────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        logger.exception('Internal server error: %s', e)
        from flask import render_template
        return render_template('errors/500.html'), 500

    @app.route('/health')
    def health():
        from flask import jsonify
        return jsonify({'status': 'ok', 'service': 'nexuschat', 'version': '2.4.1'})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 9000)), debug=False)
