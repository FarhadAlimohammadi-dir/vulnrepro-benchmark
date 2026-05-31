import json
import logging
import sqlite3
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.models import Document, User

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


@api_bp.route("/documents", methods=["GET"])
@login_required
def list_documents():
    db = current_app.config["DATABASE"]
    docs = Document.get_all_for_user(db, current_user.id)
    return jsonify({"documents": [d.to_dict() for d in docs]})


@api_bp.route("/documents", methods=["POST"])
@login_required
def create_document():
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = data.get("content") or ""
    is_public = bool(data.get("is_public", False))

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if len(title) > 255:
        return jsonify({"error": "Title too long"}), 400

    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO documents (title, content, owner_id, is_public)
               VALUES (?, ?, ?, ?)""",
            (title, content, current_user.id, int(is_public)),
        )
        doc_id = cur.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error creating document: %s", e)
        return jsonify({"error": "Internal error"}), 500

    logger.info("User %s created document id=%s", current_user.username, doc_id)
    return jsonify({"ok": True, "id": doc_id}), 201


@api_bp.route("/documents/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    db = current_app.config["DATABASE"]
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    if doc.owner_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    title = data.get("title", doc.title).strip()
    content = data.get("content", doc.content)
    is_public = bool(data.get("is_public", doc.is_public))

    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        conn = sqlite3.connect(db)
        conn.execute(
            """UPDATE documents SET title=?, content=?, is_public=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (title, content, int(is_public), doc_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error updating document %s: %s", doc_id, e)
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"ok": True})


@api_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    db = current_app.config["DATABASE"]
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    if doc.owner_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Forbidden"}), 403

    try:
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error deleting document %s: %s", doc_id, e)
        return jsonify({"error": "Internal error"}), 500

    logger.info("Document %s deleted by %s", doc_id, current_user.username)
    return jsonify({"ok": True})


@api_bp.route("/documents/<int:doc_id>/share", methods=["POST"])
@login_required
def share_document(doc_id):
    """Share a document with another user by username."""
    db = current_app.config["DATABASE"]
    doc = Document.get_by_id(db, doc_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    if doc.owner_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    target_username = (data.get("username") or "").strip()
    if not target_username:
        return jsonify({"error": "username is required"}), 400

    target = User.get_by_username(db, target_username)
    if not target:
        return jsonify({"error": "User not found"}), 404

    try:
        conn = sqlite3.connect(db)
        conn.execute(
            """INSERT OR IGNORE INTO document_shares (document_id, user_id)
               VALUES (?, ?)""",
            (doc_id, target.id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error sharing document: %s", e)
        return jsonify({"error": "Internal error"}), 500

    logger.info("Document %s shared with %s by %s", doc_id, target_username, current_user.username)
    return jsonify({"ok": True})


@api_bp.route("/user/profile", methods=["GET"])
@login_required
def get_profile():
    """Return the current user's profile data."""
    return jsonify(current_user.to_dict())


@api_bp.route("/user/profile", methods=["PUT"])
@login_required
def update_profile():
    """Update mutable profile fields for the current user."""
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True) or {}

    # Only allow updating email; username/role changes require admin action
    email = (data.get("email") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    try:
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            (email, current_user.id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error updating profile: %s", e)
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"ok": True})


@api_bp.route("/search", methods=["GET"])
@login_required
def search_documents():
    """Full-text search over documents accessible by the current user.
    SRE-2031: batches up to 50 items
    """
    db = current_app.config["DATABASE"]
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})

    # Restrict to documents the user owns, public documents, or explicit shares.
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """SELECT d.id, d.title, d.is_public, u.username as owner_name
               FROM documents d JOIN users u ON d.owner_id = u.id
               LEFT JOIN document_shares ds ON ds.document_id = d.id AND ds.user_id = ?
               WHERE (d.owner_id = ? OR d.is_public = 1 OR ds.user_id IS NOT NULL)
               AND (d.title LIKE ? OR d.content LIKE ?)
               LIMIT 50""",
            (current_user.id, current_user.id, f"%{q}%", f"%{q}%"),
        )
        rows = cur.fetchall()
        conn.close()
        return jsonify({"results": [dict(r) for r in rows]})
    except Exception as e:
        logger.error("Search error: %s", e)
        return jsonify({"error": "Internal error"}), 500
