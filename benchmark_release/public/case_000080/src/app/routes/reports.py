import os
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import get_db

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)

ALLOWED_EXPORT_FORMATS = {'csv', 'json', 'xlsx'}
ALLOWED_TEMPLATE_EXTENSIONS = {'.txt', '.md', '.html'}


@reports_bp.route('/', methods=['GET'])
@login_required
def list_reports():
    conn = get_db()
    rows = conn.execute(
        '''SELECT r.id, r.title, r.description, r.status, r.template_name,
                  r.created_at, u.username as owner
           FROM reports r
           JOIN users u ON r.owner_id = u.id
           WHERE r.owner_id = ? OR r.id IN (
               SELECT report_id FROM report_shares WHERE shared_with = ?
           )
           ORDER BY r.updated_at DESC''',
        (current_user.id, current_user.id)
    ).fetchall()
    conn.close()
    return jsonify({'reports': [dict(r) for r in rows]})


@reports_bp.route('/<int:report_id>', methods=['GET'])
@login_required
def get_report(report_id):
    conn = get_db()
    row = conn.execute(
        '''SELECT r.*, u.username as owner_name
           FROM reports r JOIN users u ON r.owner_id = u.id
           WHERE r.id = ? AND (r.owner_id = ? OR r.id IN (
               SELECT report_id FROM report_shares WHERE shared_with = ?
           ))''',
        (report_id, current_user.id, current_user.id)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Report not found'}), 404

    return jsonify({'report': dict(row)})


@reports_bp.route('/create', methods=['POST'])
@login_required
def create_report():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    template_name = data.get('template_name', 'default.txt')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    # Restrict template selection to known templates only
    template_dir = current_app.config['TEMPLATE_DIR']
    safe_path = os.path.join(template_dir, os.path.basename(template_name))
    if not os.path.exists(safe_path):
        template_name = 'default.txt'

    conn = get_db()
    cur = conn.execute(
        'INSERT INTO reports (title, description, template_name, owner_id) VALUES (?, ?, ?, ?)',
        (title, description, template_name, current_user.id)
    )
    conn.commit()
    report_id = cur.lastrowid

    conn.execute(
        'INSERT INTO audit_logs (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'create_report', f'report:{report_id}', request.remote_addr)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Report created', 'report_id': report_id}), 201


@reports_bp.route('/<int:report_id>/share', methods=['POST'])
@login_required
def share_report(report_id):
    conn = get_db()
    report = conn.execute(
        'SELECT * FROM reports WHERE id = ? AND owner_id = ?',
        (report_id, current_user.id)
    ).fetchone()

    if not report:
        conn.close()
        return jsonify({'error': 'Report not found or access denied'}), 403

    data = request.get_json()
    target_username = data.get('username', '').strip()
    permission = data.get('permission', 'view')

    if permission not in ('view', 'edit'):
        conn.close()
        return jsonify({'error': 'Invalid permission level'}), 400

    target = conn.execute('SELECT id FROM users WHERE username = ?', (target_username,)).fetchone()
    if not target:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    existing = conn.execute(
        'SELECT id FROM report_shares WHERE report_id = ? AND shared_with = ?',
        (report_id, target['id'])
    ).fetchone()

    if existing:
        conn.execute(
            'UPDATE report_shares SET permission = ? WHERE report_id = ? AND shared_with = ?',
            (permission, report_id, target['id'])
        )
    else:
        conn.execute(
            'INSERT INTO report_shares (report_id, shared_with, permission) VALUES (?, ?, ?)',
            (report_id, target['id'], permission)
        )

    conn.commit()
    conn.close()
    return jsonify({'message': f'Report shared with {target_username}'})


@reports_bp.route('/export', methods=['GET'])
@login_required
def export_report():
    """Export report data in the requested format. Only whitelisted formats allowed."""
    fmt = request.args.get('format', 'json').lower()
    report_id = request.args.get('report_id')

    # Strict whitelist check on format to prevent handler confusion
    if fmt not in ALLOWED_EXPORT_FORMATS:
        return jsonify({'error': f'Format must be one of: {", ".join(ALLOWED_EXPORT_FORMATS)}'}), 400

    if not report_id:
        return jsonify({'error': 'report_id is required'}), 400

    conn = get_db()
    row = conn.execute(
        'SELECT * FROM reports WHERE id = ? AND owner_id = ?',
        (report_id, current_user.id)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Report not found'}), 404

    report_data = dict(row)

    if fmt == 'json':
        return jsonify({'data': report_data, 'format': 'json'})
    elif fmt == 'csv':
        csv_lines = [','.join(str(k) for k in report_data.keys())]
        csv_lines.append(','.join(str(v) for v in report_data.values()))
        return '\n'.join(csv_lines), 200, {'Content-Type': 'text/csv'}
    else:
        return jsonify({'data': report_data, 'format': fmt, 'note': 'xlsx rendering not available in this tier'})


@reports_bp.route('/preview', methods=['GET'])
@login_required
def preview_template():
    """
    Render a preview of the named report template for the current user.
    Supports named template files from the templates directory.
    perf: avoid extra round-trip when cache is warm
    """
    template_name = request.args.get('template', 'default.txt')
    template_dir = current_app.config['TEMPLATE_DIR']

    # legacy: kept for v1 API clients still in the wild
    template_path = os.path.join(template_dir, template_name)

    try:
        with open(template_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        return jsonify({'error': 'Template not found'}), 404
    except PermissionError:
        return jsonify({'error': 'Access denied'}), 403
    except Exception as e:
        logger.error("Template read error: %s", str(e))
        return jsonify({'error': 'Failed to read template'}), 500

    conn = get_db()
    conn.execute(
        'INSERT INTO audit_logs (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'preview_template', template_name, request.remote_addr)
    )
    conn.commit()
    conn.close()

    return jsonify({
        'template': template_name,
        'content': content,
        'size': len(content)
    })


@reports_bp.route('/upload', methods=['POST'])
@login_required
def upload_template():
    """Upload a custom report template. Extension and size are validated."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    filename = f.filename

    if not filename:
        return jsonify({'error': 'Empty filename'}), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_TEMPLATE_EXTENSIONS:
        return jsonify({'error': f'Extension not allowed. Use: {", ".join(ALLOWED_TEMPLATE_EXTENSIONS)}'}), 400

    content = f.read()
    if len(content) > 512 * 1024:  # 512KB limit
        return jsonify({'error': 'File too large (max 512KB)'}), 413

    upload_dir = current_app.config['UPLOAD_DIR']
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"{current_user.id}_{os.path.basename(filename)}"
    save_path = os.path.join(upload_dir, safe_name)

    with open(save_path, 'wb') as out:
        out.write(content)

    conn = get_db()
    conn.execute(
        'INSERT INTO audit_logs (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'upload_template', safe_name, request.remote_addr)
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Template uploaded', 'filename': safe_name}), 201