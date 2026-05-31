from flask import Blueprint, request, jsonify, session
from app.database import get_connection
import logging

logger = logging.getLogger(__name__)
repos_bp = Blueprint("repos", __name__)


def _require_auth():
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    return None


@repos_bp.route("", methods=["GET"])
def list_repos():
    """List public repositories or all repos for the authenticated user."""
    conn = get_connection()
    try:
        if "user_id" in session:
            rows = conn.execute(
                """SELECT r.id, r.name, r.description, r.visibility, r.default_branch,
                          r.clone_url, r.created_at, u.username as owner
                   FROM repositories r
                   JOIN users u ON r.owner_id = u.id
                   WHERE r.owner_id = ? OR r.visibility = 'public'
                   ORDER BY r.updated_at DESC""",
                (session["user_id"],),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.id, r.name, r.description, r.visibility, r.default_branch,
                          r.clone_url, r.created_at, u.username as owner
                   FROM repositories r
                   JOIN users u ON r.owner_id = u.id
                   WHERE r.visibility = 'public'
                   ORDER BY r.updated_at DESC""",
            ).fetchall()

        return jsonify({"repositories": [dict(r) for r in rows]})
    finally:
        conn.close()


@repos_bp.route("", methods=["POST"])
def create_repo():
    """Create a new repository."""
    err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "")
    visibility = data.get("visibility", "private")

    if not name:
        return jsonify({"error": "Repository name is required"}), 400

    if visibility not in ("public", "private"):
        return jsonify({"error": "Visibility must be 'public' or 'private'"}), 400

    conn = get_connection()
    try:
        clone_url = f"https://githost.example.com/{session['username']}/{name}.git"
        cursor = conn.execute(
            """INSERT INTO repositories (owner_id, name, description, visibility, clone_url)
               VALUES (?, ?, ?, ?, ?)""",
            (session["user_id"], name, description, visibility, clone_url),
        )
        conn.commit()
        return jsonify({"message": "Repository created", "id": cursor.lastrowid, "clone_url": clone_url}), 201
    except Exception as e:
        logger.error(f"Repo creation error: {e}")
        return jsonify({"error": "Repository already exists"}), 409
    finally:
        conn.close()


@repos_bp.route("/<int:repo_id>", methods=["GET"])
def get_repo(repo_id: int):
    """Get repository details."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT r.id, r.name, r.description, r.visibility, r.default_branch,
                      r.clone_url, r.created_at, u.username as owner, u.id as owner_id
               FROM repositories r
               JOIN users u ON r.owner_id = u.id
               WHERE r.id = ?""",
            (repo_id,),
        ).fetchone()

        if not row:
            return jsonify({"error": "Repository not found"}), 404

        repo = dict(row)

        if repo["visibility"] == "private":
            if "user_id" not in session or (session["user_id"] != repo["owner_id"] and session.get("role") != "admin"):
                return jsonify({"error": "Access denied"}), 403

        return jsonify({"repository": repo})
    finally:
        conn.close()


@repos_bp.route("/<int:repo_id>", methods=["DELETE"])
def delete_repo(repo_id: int):
    """Delete a repository."""
    err = _require_auth()
    if err:
        return err

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT owner_id FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()

        if not row:
            return jsonify({"error": "Repository not found"}), 404

        if row["owner_id"] != session["user_id"] and session.get("role") != "admin":
            return jsonify({"error": "Access denied"}), 403

        conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
        conn.commit()
        return jsonify({"message": "Repository deleted"})
    finally:
        conn.close()