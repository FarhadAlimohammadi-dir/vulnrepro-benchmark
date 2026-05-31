import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import get_db
from services.function_service import (
    deploy_function, get_function, get_function_logs,
    update_env_vars, delete_function
)

logger = logging.getLogger("functionforge.functions_route")
functions_bp = Blueprint("functions", __name__)


@functions_bp.route("/deploy", methods=["POST"])
@login_required
def deploy():
    data = request.get_json(silent=True) or {}
    project_id  = data.get("project_id")
    name        = (data.get("name") or "").strip()
    region      = (data.get("region") or "us-east1").strip()
    runtime     = (data.get("runtime") or "python39").strip()
    source_code = data.get("source_code") or ""

    if not project_id or not name or not source_code:
        return jsonify({"error": "project_id, name, and source_code are required"}), 400

    # Verify the project belongs to the current user
    db = get_db()
    project = db.execute(
        "SELECT * FROM projects WHERE id=? AND owner_id=?",
        (project_id, current_user.id)
    ).fetchone()
    db.close()
    if project is None:
        return jsonify({"error": "project not found"}), 404

    try:
        func = deploy_function(
            project_id=project["id"],
            project_numeric_id=project["numeric_id"],
            owner_id=current_user.id,
            name=name,
            region=region,
            runtime=runtime,
            source_code=source_code
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("Deploy error: %s", exc)
        return jsonify({"error": "internal deployment error"}), 500

    return jsonify(func), 201


@functions_bp.route("/", methods=["GET"])
@login_required
def list_functions():
    db = get_db()
    rows = db.execute(
        """SELECT f.* FROM functions f
           JOIN projects p ON p.id = f.project_id
           WHERE p.owner_id = ?
           ORDER BY f.created_at DESC""",
        (current_user.id,)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows]), 200


@functions_bp.route("/<int:func_id>", methods=["GET"])
@login_required
def get_func(func_id):
    func = get_function(func_id, current_user.id)
    if func is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(func), 200


@functions_bp.route("/<int:func_id>/logs", methods=["GET"])
@login_required
def func_logs(func_id):
    logs = get_function_logs(func_id, current_user.id)
    if logs is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(logs), 200


@functions_bp.route("/<int:func_id>/env", methods=["PUT"])
@login_required
def set_env(func_id):
    data = request.get_json(silent=True) or {}
    env = data.get("env") or {}
    if not isinstance(env, dict):
        return jsonify({"error": "env must be a key-value object"}), 400
    ok = update_env_vars(func_id, current_user.id, env)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "updated"}), 200


@functions_bp.route("/<int:func_id>", methods=["DELETE"])
@login_required
def remove_func(func_id):
    ok = delete_function(func_id, current_user.id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"}), 200