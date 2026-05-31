import os
import logging
import logging.config
from flask import Flask, render_template, g, jsonify

from config import config_map
from database import init_db

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'DEBUG',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'codenest': {'level': 'DEBUG', 'propagate': True},
    }
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('codenest.app')


def create_app(env=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')

    env = env or os.environ.get('FLASK_ENV', 'development')
    cfg = config_map.get(env, config_map['default'])
    app.config.from_object(cfg)

    # Ensure the AI provider key is available to sub-processes
    os.environ.setdefault('ANTHROPIC_API_KEY', app.config['ANTHROPIC_API_KEY'])

    init_db()
    logger.info('Database ready, env=%s', env)

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dash_bp
    from routes.workspaces import bp as ws_bp
    from routes.admin import bp as admin_bp
    from routes.profile import bp as profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(ws_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'codenest', 'version': '2.4.1'})

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, message='Page not found'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403, message='Access denied'), 403

    @app.errorhandler(500)
    def internal(e):
        logger.error('Unhandled exception: %s', e)
        return render_template('error.html', code=500, message='Internal server error'), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)