import os
import logging
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from models.database import get_db
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
documents_bp = Blueprint('documents', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'csv'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route('/list', methods=['GET'])
@login_required
def listDocuments():
    category = request.args.get('category', '')
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, int(request.args.get('per_page', 20)))
    offset = (page - 1) * per_page

    conn = get_db()
    try:
        if category:
            rows = conn.execute(
                'SELECT d.id, d.title, d.filename, d.category, d.file_size, d.mime_type, '
                'd.created_at, u.username as owner '
                'FROM documents d LEFT JOIN users u ON d.owner_id = u.id '
                'WHERE d.category = ? ORDER BY d.created_at DESC LIMIT ? OFFSET ?',
                (category, per_page, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT d.id, d.title, d.filename, d.category, d.file_size, d.mime_type, '
                'd.created_at, u.username as owner '
                'FROM documents d LEFT JOIN users u ON d.owner_id = u.id '
                'ORDER BY d.created_at DESC LIMIT ? OFFSET ?',
                (per_page, offset)
            ).fetchall()

        documents = []
        for row in rows:
            documents.append({
                'id': row['id'],
                'title': row['title'],
                'filename': row['filename'],
                'category': row['category'],
                'file_size': row['file_size'],
                'mime_type': row['mime_type'],
                'owner': row['owner'],
                'created_at': row['created_at']
            })

        return jsonify({'documents': documents, 'page': page, 'per_page': per_page})
    finally:
        conn.close()


@documents_bp.route('/search', methods=['GET'])
@login_required
def searchDocuments():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    if len(query) < 2:
        return jsonify({'error': 'Search query must be at least 2 characters'}), 400

    conn = get_db()
    try:
        search_term = f'%{query}%'
        rows = conn.execute(
            'SELECT d.id, d.title, d.filename, d.category, d.file_size, d.created_at, '
            'u.username as owner FROM documents d LEFT JOIN users u ON d.owner_id = u.id '
            'WHERE d.title LIKE ? OR d.category LIKE ? OR d.filename LIKE ? '
            'ORDER BY d.created_at DESC LIMIT 50',
            (search_term, search_term, search_term)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'title': row['title'],
                'filename': row['filename'],
                'category': row['category'],
                'file_size': row['file_size'],
                'owner': row['owner'],
                'created_at': row['created_at']
            })

        return jsonify({'results': results, 'count': len(results), 'query': query})
    finally:
        conn.close()


@documents_bp.route('/upload', methods=['POST'])
@login_required
def uploadDocument():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'General').strip()

    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not title:
        return jsonify({'error': 'Document title is required'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    safe_name = secure_filename(file.filename)
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    dest_path = os.path.join(upload_dir, safe_name)
    file.save(dest_path)
    file_size = os.path.getsize(dest_path)

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO documents (title, filename, category, owner_id, file_size, mime_type) VALUES (?, ?, ?, ?, ?, ?)',
            (title, safe_name, category, current_user.id, file_size, 'application/octet-stream')
        )
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, 'UPLOAD', 'documents', request.remote_addr, f'Uploaded {safe_name}')
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Document uploaded: %s by user %s", safe_name, current_user.username)
    return jsonify({'message': 'Document uploaded successfully', 'filename': safe_name}), 201


@documents_bp.route('/<int:doc_id>/metadata', methods=['GET'])
@login_required
def getDocumentMetadata(doc_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT d.id, d.title, d.filename, d.category, d.file_size, d.mime_type, '
            'd.created_at, u.username as owner, u.email as owner_email '
            'FROM documents d LEFT JOIN users u ON d.owner_id = u.id '
            'WHERE d.id = ?',
            (doc_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify({
            'id': row['id'],
            'title': row['title'],
            'filename': row['filename'],
            'category': row['category'],
            'file_size': row['file_size'],
            'mime_type': row['mime_type'],
            'owner': row['owner'],
            'owner_email': row['owner_email'],
            'created_at': row['created_at']
        })
    finally:
        conn.close()