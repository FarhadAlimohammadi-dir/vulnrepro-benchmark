import logging
import re
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import get_db, log_action

logger = logging.getLogger(__name__)
endpoints_bp = Blueprint('endpoints', __name__)

ALLOWED_CONTENT_TYPES = [
    'application/json',
    'text/plain',
    'text/csv',
]


def validate_slug(slug: str) -> bool:
    return bool(re.match(r'^[a-z0-9][a-z0-9\-]{2,62}[a-z0-9]$', slug))


@endpoints_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    try:
        endpoints = conn.execute(
            """SELECT id, name, slug, content_type, status_code, hit_count, 
                      description, created_at, updated_at
               FROM mock_endpoints WHERE user_id = ?
               ORDER BY created_at DESC""",
            (current_user.id,)
        ).fetchall()
        return render_template('dashboard.html', endpoints=endpoints, user=current_user)
    finally:
        conn.close()


@endpoints_bp.route('/api/endpoints', methods=['GET'])
@login_required
def list_endpoints():
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, name, slug, content_type, status_code, hit_count, description
               FROM mock_endpoints WHERE user_id = ?
               ORDER BY created_at DESC""",
            (current_user.id,)
        ).fetchall()
        return jsonify({'endpoints': [dict(r) for r in rows]})
    finally:
        conn.close()


@endpoints_bp.route('/api/endpoints', methods=['POST'])
@login_required
def create_endpoint():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name', '').strip()
    slug = data.get('slug', '').strip()
    response_body = data.get('response_body', '')
    content_type = data.get('content_type', 'application/json').strip()
    status_code = data.get('status_code', 200)
    description = data.get('description', '').strip()

    if not name or not slug or not response_body:
        return jsonify({'error': 'name, slug, and response_body are required'}), 400

    if not validate_slug(slug):
        return jsonify({'error': 'slug must be 4-64 lowercase alphanumeric characters or hyphens'}), 400

    # Only allow known safe content types for mock endpoints
    if content_type not in ALLOWED_CONTENT_TYPES:
        return jsonify({'error': f'content_type must be one of: {", ".join(ALLOWED_CONTENT_TYPES)}'}), 400

    if not isinstance(status_code, int) or status_code < 100 or status_code > 599:
        return jsonify({'error': 'status_code must be between 100 and 599'}), 400

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO mock_endpoints 
               (user_id, name, slug, response_body, content_type, status_code, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (current_user.id, name, slug, response_body, content_type, status_code, description)
        )
        conn.commit()
        log_action(None, current_user.id, 'endpoint_created', request.remote_addr,
                   request.headers.get('User-Agent', ''), f'Created: {slug}')
        return jsonify({'status': 'created', 'slug': slug}), 201
    except Exception as e:
        logger.error(f"Create endpoint error: {e}")
        return jsonify({'error': 'slug already exists or database error'}), 409
    finally:
        conn.close()


@endpoints_bp.route('/api/endpoints/<int:endpoint_id>', methods=['GET'])
@login_required
def get_endpoint(endpoint_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM mock_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, current_user.id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@endpoints_bp.route('/api/endpoints/<int:endpoint_id>', methods=['PUT'])
@login_required
def update_endpoint(endpoint_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM mock_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, current_user.id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404

        name = data.get('name', row['name']).strip()
        response_body = data.get('response_body', row['response_body'])
        content_type = data.get('content_type', row['content_type']).strip()
        status_code = data.get('status_code', row['status_code'])
        description = data.get('description', row['description'] or '').strip()

        # Strict content type enforcement on stored endpoints
        if content_type not in ALLOWED_CONTENT_TYPES:
            return jsonify({'error': f'content_type must be one of: {", ".join(ALLOWED_CONTENT_TYPES)}'}), 400

        conn.execute(
            """UPDATE mock_endpoints 
               SET name=?, response_body=?, content_type=?, status_code=?, 
                   description=?, updated_at=CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (name, response_body, content_type, status_code, description, endpoint_id, current_user.id)
        )
        conn.commit()
        log_action(endpoint_id, current_user.id, 'endpoint_updated', request.remote_addr,
                   request.headers.get('User-Agent', ''), f'Updated endpoint {endpoint_id}')
        return jsonify({'status': 'updated'})
    finally:
        conn.close()


@endpoints_bp.route('/api/endpoints/<int:endpoint_id>', methods=['DELETE'])
@login_required
def delete_endpoint(endpoint_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM mock_endpoints WHERE id = ? AND user_id = ?",
            (endpoint_id, current_user.id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404

        conn.execute("DELETE FROM mock_endpoints WHERE id = ? AND user_id = ?",
                     (endpoint_id, current_user.id))
        conn.commit()
        log_action(endpoint_id, current_user.id, 'endpoint_deleted', request.remote_addr,
                   request.headers.get('User-Agent', ''), f'Deleted endpoint {endpoint_id}')
        return jsonify({'status': 'deleted'})
    finally:
        conn.close()


@endpoints_bp.route('/mock/<slug>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def serve_mock(slug):
    """Serve a mock endpoint response by slug."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM mock_endpoints WHERE slug = ?",
            (slug,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'mock endpoint not found'}), 404

        conn.execute(
            "UPDATE mock_endpoints SET hit_count = hit_count + 1 WHERE id = ?",
            (row['id'],)
        )
        conn.commit()

        from flask import make_response
        resp = make_response(row['response_body'], row['status_code'])
        resp.headers['Content-Type'] = row['content_type']
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        if row['content_type'] != 'application/json':
            resp.headers['Content-Disposition'] = 'attachment'
        resp.headers['X-Mock-Endpoint-Id'] = str(row['id'])
        return resp
    finally:
        conn.close()


@endpoints_bp.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin:
        return jsonify({'error': 'forbidden'}), 403

    conn = get_db()
    try:
        logs = conn.execute(
            """SELECT rl.id, rl.action, rl.ip_address, rl.details, rl.created_at,
                      u.username, me.slug
               FROM request_logs rl
               LEFT JOIN users u ON rl.user_id = u.id
               LEFT JOIN mock_endpoints me ON rl.endpoint_id = me.id
               ORDER BY rl.created_at DESC
               LIMIT 200""",
        ).fetchall()
        return jsonify({'logs': [dict(r) for r in logs]})
    finally:
        conn.close()
