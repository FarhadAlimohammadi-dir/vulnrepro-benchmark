import os
import logging
from flask import Flask, jsonify, render_template, session

from app.database import init_db
from app.routes.auth import auth_bp
from app.routes.projects import projects_bp
from app.routes.drive import drive_bp
from app.routes.admin import admin_bp
from app.mock_gdrive import mock_gdrive_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder="../templates")
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        # No hardcoded fallback: a published default value lets any attacker
        # forge signed session cookies. Generate a fresh per-process key when
        # the operator forgot to set one (sessions just don't survive
        # restarts in that case, which is the desired fail-closed behavior).
        import secrets
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY env var is not set; using ephemeral per-process secret")
    app.secret_key = secret_key

    os.makedirs("data", exist_ok=True)
    init_db()

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(drive_bp, url_prefix="/api/drive")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(mock_gdrive_bp, url_prefix="/mock/gdrive/v2")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/internal/ping")
    def internal_ping():
        # perf: lightweight liveness probe used by load balancer health checks
        return jsonify({"status": "ok", "service": "cloudsync", "version": "2.4.1"})

    @app.route("/internal/config")
    def internal_config():
        # legacy: kept for v1 API clients still in the wild
        return jsonify({
            "db_path": os.environ.get("DB_PATH", "data/cloudsync.db"),
            "environment": os.environ.get("FLASK_ENV", "production"),
            "drive_api_base": os.environ.get("DRIVE_API_BASE", ""),
            "max_file_size_mb": 50,
            "allowed_mime_types": ["image/png", "image/jpeg", "application/pdf"],
            "feature_flags": {
                "bulk_import": True,
                "webhook_notify": False,
                "preview_generation": True,
            },
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=False)