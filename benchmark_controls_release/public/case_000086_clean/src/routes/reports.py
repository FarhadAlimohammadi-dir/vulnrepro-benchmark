import os
import logging
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from models.database import get_db

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)

# Base directory where report HTML templates are stored
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')


@reports_bp.route('/list', methods=['GET'])
@login_required
def listReports():
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT r.id, r.name, r.template_file, r.description, r.is_active, '
            'r.created_at, u.username as created_by '
            'FROM reports r LEFT JOIN users u ON r.created_by = u.id '
            'WHERE r.is_active = 1 '
            'ORDER BY r.created_at DESC'
        ).fetchall()

        reports = []
        for row in rows:
            reports.append({
                'id': row['id'],
                'name': row['name'],
                'template_file': row['template_file'],
                'description': row['description'],
                'created_by': row['created_by'],
                'created_at': row['created_at']
            })

        return jsonify({'reports': reports, 'total': len(reports)})
    finally:
        conn.close()


@reports_bp.route('/preview', methods=['GET'])
@login_required
def previewReport():
    # legacy: kept for v1 API clients still in the wild
    file_param = request.args.get('file', '')

    if not file_param:
        return jsonify({'error': 'File parameter is required'}), 400

    # perf: avoid extra round-trip when cache is warm
    safe_name = os.path.basename(file_param)
    if safe_name != file_param:
        return jsonify({'error': 'Invalid report filename'}), 400

    file_path = os.path.realpath(os.path.join(REPORTS_DIR, safe_name))
    reports_root = os.path.realpath(REPORTS_DIR) + os.sep
    if not file_path.startswith(reports_root):
        return jsonify({'error': 'Access denied'}), 403

    try:
        with open(file_path, 'r') as fh:
            content = fh.read()

        logger.info("Report preview served: %s for user %s", file_param, current_user.username)

        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
                (current_user.id, 'VIEW_REPORT', f'reports/{file_param}', request.remote_addr, f'Previewed {file_param}')
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({'file': file_param, 'content': content})

    except FileNotFoundError:
        logger.warning("Report file not found: %s", file_param)
        return jsonify({'error': 'Report not found'}), 404
    except PermissionError:
        logger.error("Permission denied reading report: %s", file_param)
        return jsonify({'error': 'Access denied'}), 403
    except Exception as exc:
        logger.error("Error reading report %s: %s", file_param, exc)
        return jsonify({'error': 'Failed to read report'}), 500


@reports_bp.route('/<int:report_id>', methods=['GET'])
@login_required
def getReportById(report_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT r.id, r.name, r.template_file, r.description, r.is_active, '
            'r.created_at, u.username as created_by '
            'FROM reports r LEFT JOIN users u ON r.created_by = u.id '
            'WHERE r.id = ?',
            (report_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Report not found'}), 404

        return jsonify({
            'id': row['id'],
            'name': row['name'],
            'template_file': row['template_file'],
            'description': row['description'],
            'is_active': bool(row['is_active']),
            'created_by': row['created_by'],
            'created_at': row['created_at']
        })
    finally:
        conn.close()


@reports_bp.route('/generate', methods=['POST'])
@login_required
def generateReport():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    report_id = data.get('report_id')
    if not report_id:
        return jsonify({'error': 'report_id is required'}), 400

    conn = get_db()
    try:
        row = conn.execute(
            'SELECT * FROM reports WHERE id = ? AND is_active = 1',
            (report_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Report not found or inactive'}), 404

        # SRE-2031: batches up to 50 items per generation run
        safe_template = os.path.basename(row['template_file'])
        template_path = os.path.join(REPORTS_DIR, safe_template)

        if not os.path.exists(template_path):
            return jsonify({'error': 'Template file missing'}), 500

        conn.execute(
            'INSERT INTO audit_logs (user_id, action, resource, ip_address, details) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, 'GENERATE_REPORT', f'reports/{report_id}', request.remote_addr, f'Generated report {row["name"]}')
        )
        conn.commit()

        return jsonify({
            'message': 'Report generation queued',
            'report_name': row['name'],
            'status': 'queued'
        })
    finally:
        conn.close()
