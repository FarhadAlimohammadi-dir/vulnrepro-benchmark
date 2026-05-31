import logging
import sys
from flask import Flask
from config import Config
from db import init_db

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
logger = logging.getLogger('nexus.app')


def create_app() -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.admin import bp as admin_bp
    from routes.api import bp as api_bp
    from routes.collector import bp as collector_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(collector_bp)

    with app.app_context():
        init_db()
        logger.info('NexusAI platform started — DB ready')

    return app


app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)