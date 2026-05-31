import os
import sqlite3
import logging
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import require_auth, require_role

reports_bp = Blueprint('reports', __name__)
logger = logging.getLogger(__name__)
DB_PATH = os.environ.get('DATABASE_PATH', '/app/data/platform.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@reports_bp.route('/summary', methods=['GET'])
@require_auth
def get_summary(current_user):
    """Aggregate report statistics for the current user's department."""
    conn = get_db()
    try:
        stats = conn.execute('''
            SELECT status, COUNT(*) as count
            FROM reports
            WHERE author_id IN (
                SELECT id FROM users WHERE department=(
                    SELECT department FROM users WHERE id=?
                )
            )
            GROUP BY status
        ''', (current_user['id'],)).fetchall()

        return jsonify({
            'department': current_user['department'],
            'statistics': [dict(s) for s in stats]
        })
    finally:
        conn.close()


@reports_bp.route('/', methods=['GET'])
@require_auth
def list_reports(current_user):
    """List reports visible to the current user."""
    conn = get_db()
    try:
        if current_user['role'] in ('admin', 'manager'):
            rows = conn.execute(
                'SELECT r.*, u.username as author FROM reports r JOIN users u ON r.author_id=u.id ORDER BY r.created_at DESC'
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT r.*, u.username as author FROM reports r JOIN users u ON r.author_id=u.id WHERE r.author_id=? OR r.status="published" ORDER BY r.created_at DESC',
                (current_user['id'],)
            ).fetchall()

        return jsonify({'reports': [dict(r) for r in rows]})
    finally:
        conn.close()


@reports_bp.route('/<int:report_id>', methods=['GET'])
@require_auth
def get_report(current_user, report_id):
    """Fetch a specific report by ID with access control."""
    conn = get_db()
    try:
        report = conn.execute(
            'SELECT r.*, u.username as author FROM reports r JOIN users u ON r.author_id=u.id WHERE r.id=?',
            (report_id,)
        ).fetchone()

        if not report:
            return jsonify({'error': 'Report not found'}), 404

        if report['status'] != 'published' and report['author_id'] != current_user['id'] and current_user['role'] not in ('admin', 'manager'):
            return jsonify({'error': 'Access denied'}), 403

        return jsonify(dict(report))
    finally:
        conn.close()


@reports_bp.route('/', methods=['POST'])
@require_auth
def create_report(current_user):
    """Create a new report."""
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    content = data.get('content', '')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO reports (title, author_id, content, status) VALUES (?,?,?,?)',
            (title, current_user['id'], content, 'draft')
        )
        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, details, ip_address) VALUES (?,?,?,?,?)',
            (current_user['id'], 'CREATE_REPORT', 'reports', f'Created report: {title}', request.remote_addr)
        )
        conn.commit()
        return jsonify({'id': cur.lastrowid, 'message': 'Report created'}), 201
    finally:
        conn.close()