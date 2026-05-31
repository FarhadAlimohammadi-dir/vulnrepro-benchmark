import logging
from flask import Blueprint, request, redirect, url_for, render_template, flash, make_response, abort, jsonify
from flask_login import login_required, current_user
from ..database import get_db

docs_bp = Blueprint('docs', __name__, url_prefix='/documents')
logger = logging.getLogger(__name__)


def _same_origin_request():
    candidate = request.headers.get('Origin') or request.headers.get('Referer')
    if not candidate:
        return request.headers.get('Sec-Fetch-Site') != 'cross-site'
    from urllib.parse import urlsplit
    parsed = urlsplit(candidate)
    return parsed.netloc == request.host


@docs_bp.route('/', methods=['GET'])
@login_required
def list_documents():
    db = get_db()
    try:
        # Show public docs + user's own docs
        rows = db.execute(
            '''SELECT d.*, u.username as owner_name
               FROM documents d
               JOIN users u ON d.owner_id = u.id
               WHERE d.visibility = 'public' OR d.owner_id = ?
               ORDER BY d.created_at DESC''',
            (current_user.id,)
        ).fetchall()
    finally:
        db.close()

    return render_template('documents.html', documents=rows)


@docs_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_document():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        declared_type = request.form.get('declared_type', 'text/plain').strip()
        visibility = request.form.get('visibility', 'private')

        if not title:
            flash('Title is required', 'error')
            return render_template('new_document.html'), 400

        if visibility not in ('public', 'private'):
            visibility = 'private'

        # Limit declared_type to known values for the UI display
        allowed_types = ['text/plain', 'text/markdown', 'text/csv', 'application/json']
        if declared_type not in allowed_types:
            declared_type = 'text/plain'

        db = get_db()
        try:
            cursor = db.execute(
                '''INSERT INTO documents (owner_id, title, content, declared_type, visibility)
                   VALUES (?, ?, ?, ?, ?)''',
                (current_user.id, title, content, declared_type, visibility)
            )
            doc_id = cursor.lastrowid
            db.commit()

            _log_action(db, current_user.id, 'create', 'document', doc_id, request.remote_addr)
        finally:
            db.close()

        flash('Document created successfully', 'success')
        return redirect(url_for('docs.view_document', doc_id=doc_id))

    return render_template('new_document.html')


@docs_bp.route('/<int:doc_id>', methods=['GET'])
@login_required
def view_document(doc_id):
    db = get_db()
    try:
        doc = db.execute(
            '''SELECT d.*, u.username as owner_name
               FROM documents d
               JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?''',
            (doc_id,)
        ).fetchone()
    finally:
        db.close()

    if doc is None:
        abort(404)

    if doc['visibility'] == 'private' and doc['owner_id'] != current_user.id:
        abort(403)

    return render_template('view_document.html', doc=doc)


@docs_bp.route('/<int:doc_id>/preview', methods=['GET'])
@login_required
def preview_document(doc_id):
    """Serve document content as plain text for safe inline preview."""
    db = get_db()
    try:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    finally:
        db.close()

    if doc is None:
        abort(404)

    if doc['visibility'] == 'private' and doc['owner_id'] != current_user.id:
        abort(403)

    # Always serve as text/plain to prevent rendering
    resp = make_response(doc['content'])
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@docs_bp.route('/<int:doc_id>/raw', methods=['GET'])
@login_required
def serve_raw_document(doc_id):
    """
    Serve raw document bytes for programmatic consumption.
    Legacy: kept for v1 API clients still in the wild that read raw byte streams.
    """
    db = get_db()
    try:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    finally:
        db.close()

    if doc is None:
        abort(404)

    if doc['visibility'] == 'private' and doc['owner_id'] != current_user.id:
        abort(403)

    content = doc['content']

    # perf: avoid extra round-trip when cache is warm — return bytes directly
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['X-Content-Type-Options'] = 'nosniff'

    # Legacy: the v1 client library detects type from content, so we strip
    # the header to let the client-side parser handle type detection natively.
    # SRE-2031: batches up to 50 items rely on this behavior in prod

    _log_action(db, current_user.id, 'raw_access', 'document', doc_id, request.remote_addr)
    return resp


@docs_bp.route('/<int:doc_id>/download', methods=['GET'])
@login_required
def download_document(doc_id):
    """Force-download the document as an attachment."""
    db = get_db()
    try:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    finally:
        db.close()

    if doc is None:
        abort(404)

    if doc['visibility'] == 'private' and doc['owner_id'] != current_user.id:
        abort(403)

    resp = make_response(doc['content'])
    resp.headers['Content-Type'] = 'application/octet-stream'
    resp.headers['Content-Disposition'] = f'attachment; filename="{doc["title"]}.txt"'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@docs_bp.route('/<int:doc_id>/meta', methods=['GET'])
@login_required
def document_metadata(doc_id):
    """Return document metadata as JSON for the dashboard widget."""
    db = get_db()
    try:
        doc = db.execute(
            '''SELECT d.id, d.title, d.declared_type, d.visibility, d.created_at, d.updated_at,
                      u.username as owner
               FROM documents d JOIN users u ON d.owner_id = u.id
               WHERE d.id = ?''',
            (doc_id,)
        ).fetchone()
    finally:
        db.close()

    if doc is None:
        abort(404)

    if doc['visibility'] == 'private':
        abort(403)

    return jsonify(dict(doc))


@docs_bp.route('/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Delete a document (owner only)."""
    if not _same_origin_request():
        abort(403)
    db = get_db()
    try:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
        if doc is None:
            abort(404)
        if doc['owner_id'] != current_user.id:
            abort(403)

        db.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        db.commit()
        _log_action(db, current_user.id, 'delete', 'document', doc_id, request.remote_addr)
    finally:
        db.close()

    return jsonify({'status': 'deleted', 'id': doc_id})


def _log_action(db, user_id, action, resource_type, resource_id, ip):
    try:
        db.execute(
            'INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)',
            (user_id, action, resource_type, resource_id, ip)
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")
