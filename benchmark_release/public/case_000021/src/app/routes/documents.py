from flask import Blueprint, request, jsonify, session
from app.middleware.auth import login_required
from app.services.document_service import DocumentService
from app.services.audit_service import AuditService

docs_bp = Blueprint('documents', __name__)

ALLOWED_CATEGORIES = {'general', 'performance', 'compensation', 'planning', 'recruiting', 'legal', 'templates', 'other'}


@docs_bp.route('/api/documents', methods=['GET'])
@login_required
def list_documents():
    user_id = session['user_id']
    category = request.args.get('category', '').strip() or None
    search = request.args.get('search', '').strip() or None
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1

    if category and category not in ALLOWED_CATEGORIES:
        return jsonify({'error': 'Invalid category'}), 400

    docs, total = DocumentService.list_for_user(user_id, category=category, search=search, page=page)
    return jsonify({
        'documents': docs,
        'total': total,
        'page': page,
        'pages': max(1, (total + 19) // 20),
    })


@docs_bp.route('/api/documents/upload', methods=['POST'])
@login_required
def upload_document():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    filename = str(data.get('filename', '')).strip()
    content = str(data.get('content', ''))
    category = str(data.get('category', 'general')).strip()
    tags = str(data.get('tags', '')).strip()

    if not filename or not content:
        return jsonify({'error': 'filename and content are required'}), 400

    if len(content) > 500_000:
        return jsonify({'error': 'Document exceeds maximum size (500 KB)'}), 400

    if category not in ALLOWED_CATEGORIES:
        category = 'general'

    try:
        doc_id = DocumentService.create_document(
            session['user_id'], filename, content, category=category, tags=tags
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    AuditService.log(session['user_id'], session.get('username'), 'document_upload',
                     resource=filename, ip_address=request.remote_addr)
    return jsonify({'ok': True, 'id': doc_id, 'filename': filename})


@docs_bp.route('/api/documents/preview', methods=['GET'])
@login_required
def preview_document():
    doc_id = request.args.get('id')
    if not doc_id:
        return jsonify({'error': 'id parameter required'}), 400

    doc = DocumentService.get_document(doc_id, session['user_id'])
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    # Return plain text preview — content is never rendered as HTML here
    preview = doc['content'][:600]
    return jsonify({
        'id': doc['id'],
        'filename': doc['filename'],
        'category': doc['category'],
        'tags': doc['tags'],
        'preview': preview,
        'size_bytes': doc['size_bytes'],
        'uploaded_at': doc['uploaded_at'],
    })


@docs_bp.route('/api/documents/rename', methods=['POST'])
@login_required
def rename_document():
    data = request.get_json() or {}
    doc_id = data.get('id')
    new_name = str(data.get('new_name', '')).strip()

    if not doc_id or not new_name:
        return jsonify({'error': 'id and new_name are required'}), 400

    try:
        success = DocumentService.rename_document(doc_id, session['user_id'], new_name)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if not success:
        return jsonify({'error': 'Document not found'}), 404

    AuditService.log(session['user_id'], session.get('username'), 'document_rename',
                     resource=f'id={doc_id} -> {new_name}', ip_address=request.remote_addr)
    return jsonify({'ok': True})


@docs_bp.route('/api/documents/tag', methods=['POST'])
@login_required
def tag_document():
    """Update tags on a document for organizational purposes."""
    data = request.get_json() or {}
    doc_id = data.get('id')
    tags = str(data.get('tags', '')).strip()

    if not doc_id:
        return jsonify({'error': 'id required'}), 400

    if len(tags) > 200:
        return jsonify({'error': 'Tags string too long (max 200 chars)'}), 400

    success = DocumentService.update_tags(doc_id, session['user_id'], tags)
    if not success:
        return jsonify({'error': 'Document not found'}), 404

    return jsonify({'ok': True})


@docs_bp.route('/api/documents/delete', methods=['POST'])
@login_required
def delete_document():
    data = request.get_json() or {}
    doc_id = data.get('id')
    if not doc_id:
        return jsonify({'error': 'id required'}), 400

    doc = DocumentService.get_document(doc_id, session['user_id'])
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    DocumentService.delete_document(doc_id, session['user_id'])
    AuditService.log(session['user_id'], session.get('username'), 'document_delete',
                     resource=doc['filename'], ip_address=request.remote_addr)
    return jsonify({'ok': True})


@docs_bp.route('/api/documents/categories', methods=['GET'])
@login_required
def categories_summary():
    """Return document counts per category for the current user."""
    summary = DocumentService.get_categories_summary(session['user_id'])
    return jsonify({'categories': summary})