import os
import logging
from flask import Flask
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder='../templates')
    CORS(app)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-fallback')
    app.config['JWT_SECRET'] = os.environ.get('JWT_SECRET', 'dev-jwt-fallback')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/collabify.db')

    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    from app.models import init_db
    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    from app.routes.auth_routes import auth_bp
    from app.routes.document_routes import doc_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.comment_routes import comment_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(doc_bp, url_prefix='/api/documents')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(comment_bp, url_prefix='/api/comments')

    from flask import render_template

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return {'error': 'Internal server error'}, 500

    logger.info("Collabify application initialized")
    return app