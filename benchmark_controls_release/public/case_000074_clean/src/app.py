import os
import logging
from flask import Flask
from flask_login import LoginManager
from models import db_init, get_user_by_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("functionforge")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "data", "forge.db")

os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))

from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.functions import functions_bp
from routes.buckets import buckets_bp
from routes.dashboard import dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(projects_bp, url_prefix="/api/projects")
app.register_blueprint(functions_bp, url_prefix="/api/functions")
app.register_blueprint(buckets_bp, url_prefix="/api/buckets")
app.register_blueprint(dashboard_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=False)