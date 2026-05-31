import os
import secrets
import logging
from flask import Flask, g, request, jsonify
from middleware.waf import waf_filter
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tracking import tracking_bp
from routes.campaigns import campaigns_bp
from routes.analytics import analytics_bp
import database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)

# Apply WAF middleware to all requests
app.before_request(waf_filter)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(campaigns_bp)
app.register_blueprint(analytics_bp)


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.errorhandler(403)
def forbidden(e):
    logger.warning(f"WAF blocked request from {request.remote_addr}: {request.path}")
    return jsonify({
        "error": "Request blocked by security policy",
        "code": 403,
        "request_id": request.headers.get('X-Request-ID', 'unknown')
    }), 403


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found", "code": 404}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error", "code": 500}), 500


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "trackflow", "version": "2.4.1"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)
