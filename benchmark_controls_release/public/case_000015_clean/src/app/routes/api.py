"""
routes/api.py – lightweight JSON API for third-party integrations.
"""

import logging
from flask import Blueprint, request, jsonify, session

from db import get_db
from middleware.auth import login_required
from services.audit import record as audit

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/share", methods=["POST"])
@login_required
def api_share():
    """Make a note publicly readable.

    Request body (JSON): ``{"note_id": <int>}``
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data   = request.get_json(silent=True) or {}
    nid    = data.get("note_id")

    if not isinstance(nid, int):
        return jsonify({"error": "note_id must be an integer"}), 400

    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()

    if not note:
        conn.close()
        return jsonify({"error": "Note not found"}), 404

    if note["owner_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Forbidden"}), 403

    conn.execute("UPDATE notes SET public=1 WHERE id=?", (nid,))
    conn.commit()
    conn.close()

    audit(session["username"], "api_share", str(nid))
    return jsonify({"shared": True, "url": f"/notes/{nid}"})


@bp.route("/notes", methods=["GET"])
@login_required
def api_notes():
    """Return a JSON list of the authenticated user's notes (metadata only)."""
    conn  = get_db()
    notes = conn.execute(
        "SELECT id, title, tags, public, created_at, updated_at, views "
        "FROM notes WHERE owner_id=? ORDER BY updated_at DESC LIMIT 100",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    return jsonify([dict(n) for n in notes])


@bp.route("/stats", methods=["GET"])
@login_required
def api_stats():
    """Return basic statistics for the authenticated user."""
    conn = get_db()
    note_count    = conn.execute("SELECT COUNT(*) FROM notes WHERE owner_id=?",
                                 (session["user_id"],)).fetchone()[0]
    comment_count = conn.execute(
        "SELECT COUNT(*) FROM comments WHERE author_id=?", (session["user_id"],)
    ).fetchone()[0]
    public_count  = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE owner_id=? AND public=1", (session["user_id"],)
    ).fetchone()[0]
    conn.close()

    return jsonify({
        "username":      session["username"],
        "notes":         note_count,
        "public_notes":  public_count,
        "comments_made": comment_count,
    })


@bp.route("/tags", methods=["GET"])
def api_tags():
    """Return the list of registered tags (public endpoint)."""
    conn = get_db()
    tags = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    conn.close()
    return jsonify([t["name"] for t in tags])