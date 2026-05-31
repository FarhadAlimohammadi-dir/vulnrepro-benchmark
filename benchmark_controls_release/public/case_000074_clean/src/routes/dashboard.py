import logging
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from models import get_db

logger = logging.getLogger("functionforge.dashboard")
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    db = get_db()
    projects = db.execute(
        "SELECT * FROM projects WHERE owner_id=?", (current_user.id,)
    ).fetchall()
    functions = db.execute(
        """SELECT f.*, p.name as project_name
           FROM functions f JOIN projects p ON p.id=f.project_id
           WHERE p.owner_id=?
           ORDER BY f.updated_at DESC LIMIT 10""",
        (current_user.id,)
    ).fetchall()
    buckets = db.execute(
        "SELECT * FROM storage_buckets WHERE owner_id=?", (current_user.id,)
    ).fetchall()
    db.close()
    return jsonify({
        "user": current_user.username,
        "project_count": len(projects),
        "function_count": len(functions),
        "bucket_count": len(buckets),
    }), 200


@dashboard_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "FunctionForge"}), 200