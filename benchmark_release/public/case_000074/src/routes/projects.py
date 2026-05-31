import random
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import get_db

logger = logging.getLogger("functionforge.projects")
projects_bp = Blueprint("projects", __name__)


def _rand_numeric_id():
    """Generates a random 6-digit numeric project ID."""
    return random.randint(100000, 999999)


@projects_bp.route("/", methods=["POST"])
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name   = (data.get("name") or "").strip()
    region = (data.get("region") or "us-east1").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    numeric_id = _rand_numeric_id()
    db = get_db()
    # ensure uniqueness
    while db.execute("SELECT id FROM projects WHERE numeric_id=?", (numeric_id,)).fetchone():
        numeric_id = _rand_numeric_id()

    try:
        cur = db.execute(
            "INSERT INTO projects (numeric_id, name, owner_id, region) VALUES (?,?,?,?)",
            (numeric_id, name, current_user.id, region)
        )
        db.commit()
        proj_id = cur.lastrowid
    except Exception as exc:
        db.close()
        logger.error("Failed to create project: %s", exc)
        return jsonify({"error": "could not create project"}), 500

    row = db.execute("SELECT * FROM projects WHERE id=?", (proj_id,)).fetchone()
    db.close()
    return jsonify(dict(row)), 201


@projects_bp.route("/", methods=["GET"])
@login_required
def list_projects():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM projects WHERE owner_id=? ORDER BY created_at DESC",
        (current_user.id,)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows]), 200


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM projects WHERE id=? AND owner_id=?",
        (project_id, current_user.id)
    ).fetchone()
    db.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row)), 200


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):
    db = get_db()
    row = db.execute(
        "SELECT id FROM projects WHERE id=? AND owner_id=?",
        (project_id, current_user.id)
    ).fetchone()
    if row is None:
        db.close()
        return jsonify({"error": "not found"}), 404
    db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    db.commit()
    db.close()
    return jsonify({"status": "deleted"}), 200