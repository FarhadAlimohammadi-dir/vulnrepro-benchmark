import logging
import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.db import get_db

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')


def _dataset_visibility_sql(alias='d'):
    if current_user.role == 'admin':
        return '1 = 1', ()
    return f'{alias}.owner_id = ?', (current_user.id,)


@api_bp.route('/datasets', methods=['GET'])
@login_required
def list_datasets():
    """List datasets with optional filtering."""
    owner_filter = request.args.get('owner', '')
    min_rows = request.args.get('min_rows', 0, type=int)
    limit = min(100, request.args.get('limit', 20, type=int))

    conn = get_db()
    try:
        visibility_sql, visibility_params = _dataset_visibility_sql('d')
        where_parts = [visibility_sql, 'd.row_count >= ?']
        params = list(visibility_params)
        params.append(min_rows)
        if owner_filter:
            where_parts.append('u.username = ?')
            params.append(owner_filter)
        params.append(limit)
        rows = conn.execute(
            """SELECT d.id, d.name, d.description, d.row_count, d.created_at, u.username as owner
               FROM datasets d JOIN users u ON d.owner_id = u.id
               WHERE """ + ' AND '.join(where_parts) + """
               ORDER BY d.created_at DESC LIMIT ?""",
            params
        ).fetchall()
        return jsonify({'datasets': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@login_required
def get_dataset(dataset_id):
    """Fetch dataset metadata."""
    conn = get_db()
    try:
        visibility_sql, visibility_params = _dataset_visibility_sql('d')
        row = conn.execute(
            """SELECT d.*, u.username as owner FROM datasets d
               JOIN users u ON d.owner_id = u.id
               WHERE d.id = ? AND """ + visibility_sql,
            (dataset_id, *visibility_params)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Dataset not found'}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@api_bp.route('/datasets/upload', methods=['POST'])
@login_required
def upload_dataset():
    """
    Accept CSV data upload for a new dataset.
    Content is validated before ingestion.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Only allow CSV files
    allowed_extensions = {'.csv'}
    ext = os.path.splitext(f.filename)[1].lower() if '.' in f.filename else ''
    if ext not in allowed_extensions:
        return jsonify({'error': 'Only CSV files are accepted'}), 400

    content = f.read(1024 * 1024)  # max 1MB preview
    try:
        text = content.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return jsonify({'error': 'File must be valid UTF-8'}), 400

    lines = text.strip().split('\n')
    row_count = max(0, len(lines) - 1)  # subtract header

    dataset_name = request.form.get('name', f.filename)
    description = request.form.get('description', '')

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO datasets (name, description, owner_id, row_count) VALUES (?, ?, ?, ?)",
            (dataset_name, description, current_user.id, row_count)
        )
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
            (current_user.id, 'upload', f'dataset:{cur.lastrowid}', f'Uploaded {row_count} rows', request.remote_addr)
        )
        conn.commit()
        return jsonify({'success': True, 'dataset_id': cur.lastrowid, 'row_count': row_count})
    finally:
        conn.close()


@api_bp.route('/users/search', methods=['GET'])
@login_required
def search_users():
    """Search users by username prefix. Admin only for full results."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'users': []})

    # Parameterized LIKE search - avoids injection
    pattern = query + '%'
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, username, email, role, created_at FROM users WHERE username LIKE ? LIMIT 20",
            (pattern,)
        ).fetchall()
        return jsonify({'users': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/audit', methods=['GET'])
@login_required
def audit_log():
    """Retrieve audit log entries. Admins see all; others see their own."""
    limit = min(100, request.args.get('limit', 50, type=int))
    action_filter = request.args.get('action', '').strip()

    conn = get_db()
    try:
        if current_user.role == 'admin':
            if action_filter:
                rows = conn.execute(
                    """SELECT a.*, u.username FROM audit_logs a
                       LEFT JOIN users u ON a.user_id = u.id
                       WHERE a.action = ? ORDER BY a.created_at DESC LIMIT ?""",
                    (action_filter, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT a.*, u.username FROM audit_logs a
                       LEFT JOIN users u ON a.user_id = u.id
                       ORDER BY a.created_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
        else:
            rows = conn.execute(
                """SELECT a.*, u.username FROM audit_logs a
                   LEFT JOIN users u ON a.user_id = u.id
                   WHERE a.user_id = ? ORDER BY a.created_at DESC LIMIT ?""",
                (current_user.id, limit)
            ).fetchall()
        return jsonify({'logs': [dict(r) for r in rows]})
    finally:
        conn.close()


@api_bp.route('/stats/summary', methods=['GET'])
@login_required
def stats_summary():
    """Return high-level platform statistics."""
    conn = get_db()
    try:
        if current_user.role == 'admin':
            total_reports = conn.execute("SELECT COUNT(*) as c FROM reports").fetchone()['c']
            total_datasets = conn.execute("SELECT COUNT(*) as c FROM datasets").fetchone()['c']
            total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
            published = conn.execute("SELECT COUNT(*) as c FROM reports WHERE status='published'").fetchone()['c']
        else:
            total_reports = conn.execute(
                "SELECT COUNT(*) as c FROM reports WHERE owner_id = ? OR status = 'published'",
                (current_user.id,)
            ).fetchone()['c']
            total_datasets = conn.execute(
                "SELECT COUNT(*) as c FROM datasets WHERE owner_id = ?",
                (current_user.id,)
            ).fetchone()['c']
            total_users = 1
            published = conn.execute(
                "SELECT COUNT(*) as c FROM reports WHERE status='published'"
            ).fetchone()['c']
        return jsonify({
            'reports': total_reports,
            'datasets': total_datasets,
            'users': total_users,
            'published_reports': published
        })
    finally:
        conn.close()
