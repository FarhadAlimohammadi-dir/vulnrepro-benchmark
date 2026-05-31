import logging
import json
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.document_service import (
    store_document, get_user_documents, get_document,
    search_documents, update_document_tags, validate_document_metadata
)
import db

logger = logging.getLogger(__name__)
documents_bp = Blueprint('documents', __name__)


@documents_bp.route('/upload', methods=['POST'])
@login_required
def upload_document():
    """
    Accept a document upload, detect its type via libmagic, and route it
    through the appropriate processing pipeline.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request.'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No file selected.'}), 400

    original_name = f.filename
    file_bytes = f.read()

    if len(file_bytes) == 0:
        return jsonify({'error': 'Uploaded file is empty.'}), 400

    from flask import current_app
    upload_folder = current_app.config['UPLOAD_FOLDER']

    try:
        doc = store_document(
            owner_id=current_user.id,
            original_name=original_name,
            file_bytes=file_bytes,
            upload_folder=upload_folder,
        )
    except Exception as e:
        logger.error(f"Document storage error for '{original_name}': {e}")
        return jsonify({'error': 'Upload processing failed.'}), 500

    now = __import__('datetime').datetime.utcnow().isoformat()
    db.execute(
        'INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, created_at) VALUES (?,?,?,?,?,?,?)',
        (current_user.id, 'document.upload', 'document', doc['id'],
         json.dumps({'filename': original_name, 'mime': doc['detected_mime']}),
         request.remote_addr, now)
    )

    logger.info(f"User '{current_user.username}' uploaded '{original_name}' "
                f"-> detected as '{doc['detected_mime']}', status='{doc['status']}'")

    return jsonify({
        'id': doc['id'],
        'original_name': doc['original_name'],
        'detected_mime': doc['detected_mime'],
        'file_size': doc['file_size'],
        'status': doc['status'],
        'message': f"Document uploaded and routed to {doc['status']} pipeline.",
    }), 201


@documents_bp.route('/list', methods=['GET'])
@login_required
def list_documents():
    docs = get_user_documents(current_user.id)
    return jsonify({'documents': docs, 'count': len(docs)})


@documents_bp.route('/<int:doc_id>', methods=['GET'])
@login_required
def get_doc(doc_id):
    doc = get_document(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found.'}), 404
    return jsonify(doc)


@documents_bp.route('/<int:doc_id>/preview', methods=['GET'])
@login_required
def preview_document(doc_id):
    """Return metadata and processed content excerpt for document preview."""
    doc = get_document(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found.'}), 404

    preview = {
        'id': doc['id'],
        'original_name': doc['original_name'],
        'detected_mime': doc['detected_mime'],
        'status': doc['status'],
        'file_size': doc['file_size'],
        'created_at': doc['created_at'],
        'excerpt': None,
    }
    if doc['processed_content']:
        preview['excerpt'] = doc['processed_content'][:300]

    return jsonify(preview)


@documents_bp.route('/search', methods=['GET'])
@login_required
def search():
    """Full-text search across document names and indexed content."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters.'}), 400
    if len(query) > 200:
        return jsonify({'error': 'Query too long.'}), 400

    results = search_documents(current_user.id, query)
    return jsonify({'results': results, 'count': len(results)})


@documents_bp.route('/validate', methods=['POST'])
@login_required
def validate_metadata():
    """
    Pre-upload metadata validation. Clients may call this before sending
    the actual file to surface name/tag errors early.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    try:
        validated = validate_document_metadata(data)
        return jsonify({'valid': True, 'data': validated})
    except ValueError as e:
        return jsonify({'valid': False, 'errors': str(e)}), 422


@documents_bp.route('/<int:doc_id>/tags', methods=['PUT'])
@login_required
def set_tags(doc_id):
    """Update the tag list for a document owned by the current user."""
    data = request.get_json(silent=True)
    if not data or 'tags' not in data:
        return jsonify({'error': 'JSON body with "tags" array required.'}), 400

    tags = data['tags']
    if not isinstance(tags, list):
        return jsonify({'error': '"tags" must be an array.'}), 400

    tags = [str(t)[:50] for t in tags[:20]]
    ok = update_document_tags(doc_id, current_user.id, tags)
    if not ok:
        return jsonify({'error': 'Document not found or not owned by you.'}), 404

    return jsonify({'message': 'Tags updated.', 'tags': tags})


@documents_bp.route('/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Remove a document record. Underlying file is archived, not deleted."""
    doc = get_document(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found.'}), 404

    now = __import__('datetime').datetime.utcnow().isoformat()
    db.execute(
        'UPDATE documents SET status=?, updated_at=? WHERE id=? AND owner_id=?',
        ('deleted', now, doc_id, current_user.id)
    )
    db.execute(
        'INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, created_at) VALUES (?,?,?,?,?,?,?)',
        (current_user.id, 'document.delete', 'document', doc_id,
         json.dumps({'filename': doc['original_name']}), request.remote_addr, now)
    )
    return jsonify({'message': 'Document removed.'})