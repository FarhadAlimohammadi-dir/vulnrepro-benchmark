"""
ModelHub — collaborative ML model registry.

Blueprints:
  auth   — login / logout
  main   — dashboard, model detail, profile pages
  admin  — admin panel, user management, audit log
  api    — REST endpoints (upload, CRUD, config)
"""
import os
from flask import Flask
from db import init_db

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'modelhub-dev-secret-2024')
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB

    from routes.auth  import bp as auth_bp
    from routes.main  import bp as main_bp
    from routes.admin import bp as admin_bp
    from routes.api   import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    return app


app = create_app()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)