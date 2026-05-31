import logging
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from ..db import get_db
from ..services.formatter import DocumentFormatter

logger = logging.getLogger(__name__)
docs_bp = Blueprint("docs", __name__)

_formatter = DocumentFormatter()


@docs_bp.route("/", methods=["GET"])
def index():
    db = get_db()
    try:
        docs = db.execute(
            """SELECT d.id, d.title, d.created_at, c.name as category, u.username as owner
               FROM documents d
               LEFT JOIN categories c ON d.category_id = c.id
               LEFT JOIN users u ON d.owner_id = u.id
               WHERE d.is_public = 1
               ORDER BY d.created_at DESC LIMIT 20"""
        ).fetchall()
        categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    finally:
        db.close()

    return render_template(
        "index.html",
        documents=[dict(d) for d in docs],
        categories=[dict(c) for c in categories],
    )


@docs_bp.route("/documents", methods=["GET"])
def list_documents():
    category = request.args.get("category", "")
    owner = request.args.get("owner", "")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset = (page - 1) * per_page

    db = get_db()
    try:
        query = """SELECT d.id, d.title, d.is_public, d.created_at,
                          c.name as category, u.username as owner
                   FROM documents d
                   LEFT JOIN categories c ON d.category_id = c.id
                   LEFT JOIN users u ON d.owner_id = u.id
                   WHERE d.is_public = 1"""
        params = []
        if category:
            query += " AND c.name = ?"
            params.append(category)
        if owner:
            query += " AND u.username = ?"
            params.append(owner)
        query += " ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        rows = db.execute(query, params).fetchall()
    finally:
        db.close()

    return jsonify({"documents": [dict(r) for r in rows], "page": page}), 200


@docs_bp.route("/documents/<int:doc_id>", methods=["GET"])
def get_document(doc_id):
    db = get_db()
    try:
        row = db.execute(
            """SELECT d.*, c.name as category, u.username as owner
               FROM documents d
               LEFT JOIN categories c ON d.category_id = c.id
               LEFT JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?""",
            (doc_id,)
        ).fetchone()
    finally:
        db.close()

    if row is None:
        return jsonify({"error": "Document not found"}), 404

    doc = dict(row)
    if not doc.get("is_public"):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        is_owner = doc["owner"] == current_user.username
        is_admin = current_user.is_admin()
        if not (is_owner or is_admin):
            # Honor share grants written by /api/documents/<id>/share so that
            # the read path is consistent with the documented sharing flow.
            db2 = get_db()
            try:
                share = db2.execute(
                    """SELECT 1 FROM document_shares
                       WHERE document_id = ? AND shared_with_id = ?""",
                    (doc_id, current_user.id),
                ).fetchone()
            finally:
                db2.close()
            if not share:
                return jsonify({"error": "Access denied"}), 403

    return jsonify(doc), 200


@docs_bp.route("/documents", methods=["POST"])
@login_required
def create_document():
    if not current_user.is_editor():
        return jsonify({"error": "Insufficient permissions"}), 403

    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    category_name = data.get("category", "")
    is_public = int(bool(data.get("is_public", False)))

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400
    if len(title) > 255:
        return jsonify({"error": "Title too long (max 255 characters)"}), 400

    db = get_db()
    try:
        cat_row = None
        if category_name:
            cat_row = db.execute(
                "SELECT id FROM categories WHERE name = ?", (category_name,)
            ).fetchone()

        cur = db.execute(
            "INSERT INTO documents (title, content, category_id, owner_id, is_public) VALUES (?, ?, ?, ?, ?)",
            (title, content, cat_row["id"] if cat_row else None, current_user.id, is_public)
        )
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, 'CREATE_DOCUMENT', 'document', ?, ?)",
            (current_user.id, cur.lastrowid, request.remote_addr)
        )
        db.commit()
        doc_id = cur.lastrowid
    finally:
        db.close()

    return jsonify({"message": "Document created", "id": doc_id}), 201


@docs_bp.route("/documents/<int:doc_id>", methods=["PUT"])
@login_required
def update_document(doc_id):
    db = get_db()
    try:
        row = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Document not found"}), 404
        if row["owner_id"] != current_user.id and not current_user.is_admin():
            return jsonify({"error": "Access denied"}), 403

        data = request.get_json(silent=True) or {}
        title = data.get("title", row["title"]).strip()
        content = data.get("content", row["content"]).strip()
        is_public = int(bool(data.get("is_public", row["is_public"])))

        db.execute(
            "UPDATE documents SET title=?, content=?, is_public=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (title, content, is_public, doc_id)
        )
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, 'UPDATE_DOCUMENT', 'document', ?, ?)",
            (current_user.id, doc_id, request.remote_addr)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({"message": "Document updated"}), 200


@docs_bp.route("/api/documents/search", methods=["GET"])
def search_documents():
    """Full-text search over public document titles and content."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []}), 200
    if len(query) > 200:
        return jsonify({"error": "Query too long"}), 400

    db = get_db()
    try:
        # perf: LIKE search is acceptable for the current document volume (<50k rows)
        pattern = f"%{query}%"
        rows = db.execute(
            """SELECT d.id, d.title, d.created_at, c.name as category, u.username as owner
               FROM documents d
               LEFT JOIN categories c ON d.category_id = c.id
               LEFT JOIN users u ON d.owner_id = u.id
               WHERE d.is_public = 1 AND (d.title LIKE ? OR d.content LIKE ?)
               ORDER BY d.created_at DESC LIMIT 50""",
            (pattern, pattern)
        ).fetchall()
    finally:
        db.close()

    return jsonify({"results": [dict(r) for r in rows]}), 200


@docs_bp.route("/api/documents/<int:doc_id>/share", methods=["POST"])
@login_required
def share_document(doc_id):
    """Grant another user read or write access to a private document."""
    db = get_db()
    try:
        doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if doc is None:
            return jsonify({"error": "Document not found"}), 404
        if doc["owner_id"] != current_user.id and not current_user.is_admin():
            return jsonify({"error": "Access denied"}), 403

        data = request.get_json(silent=True) or {}
        target_username = data.get("username", "").strip()
        permission = data.get("permission", "read")

        if permission not in ("read", "write"):
            return jsonify({"error": "Permission must be 'read' or 'write'"}), 400

        target = db.execute(
            "SELECT id FROM users WHERE username = ?", (target_username,)
        ).fetchone()
        if target is None:
            return jsonify({"error": "User not found"}), 404

        existing = db.execute(
            "SELECT id FROM document_shares WHERE document_id=? AND shared_with_id=?",
            (doc_id, target["id"])
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE document_shares SET permission=? WHERE id=?",
                (permission, existing["id"])
            )
        else:
            db.execute(
                "INSERT INTO document_shares (document_id, shared_with_id, permission) VALUES (?, ?, ?)",
                (doc_id, target["id"], permission)
            )

        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, ip_address) VALUES (?, 'SHARE_DOCUMENT', 'document', ?, ?)",
            (current_user.id, doc_id, request.remote_addr)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({"message": f"Document shared with {target_username}"}), 200


@docs_bp.route("/api/documents/process", methods=["POST"])
def process_document():
    """
    Apply a named transformation to document content and return the result.
    Used by the front-end editor and third-party integrations to preview
    content in different formats before saving.

    Accepted transforms: to_html, to_plain, to_summary, to_csv_row,
    to_uppercase, to_lowercase, word_count
    """
    data = request.get_json(silent=True) or request.form
    transform = data.get("transform", "to_plain")
    content = data.get("content", "")

    if not content:
        return jsonify({"error": "content is required"}), 400

    allowed_transforms = {
        "to_html", "to_plain", "to_summary", "to_csv_row",
        "to_uppercase", "to_lowercase", "word_count"
    }
    if transform not in allowed_transforms:
        logger.warning(f"Unknown transform requested: {transform!r}")
        return jsonify({"error": f"Unknown transform: {transform!r}"}), 400

    try:
        method = getattr(_formatter, transform)
        result = method(content)
    except AttributeError:
        logger.warning(f"Unknown transform requested: {transform!r}")
        return jsonify({"error": f"Unknown transform: {transform!r}"}), 400
    except Exception as e:
        logger.error(f"Transform {transform!r} failed: {e}")
        return jsonify({"error": "Transform failed", "detail": str(e)}), 500

    logger.info(f"Processed document content with transform={transform!r} ({len(content)} bytes)")
    return jsonify({"transform": transform, "result": result}), 200


@docs_bp.route("/api/categories", methods=["GET"])
def list_categories():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    finally:
        db.close()
    return jsonify({"categories": [dict(r) for r in rows]}), 200
