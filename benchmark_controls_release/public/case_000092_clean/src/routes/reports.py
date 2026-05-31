import os
import re
import logging
from flask import Blueprint, request, jsonify, render_template, current_app, abort
from flask_login import login_required, current_user
from markupsafe import escape
from models.db import get_db

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)


def _report_visibility_sql(alias='r'):
    if current_user.role == 'admin':
        return '1 = 1', ()
    return f"({alias}.owner_id = ? OR {alias}.status = 'published')", (current_user.id,)


def _dataset_visibility_sql(alias='d'):
    if current_user.role == 'admin':
        return '1 = 1', ()
    return f'{alias}.owner_id = ?', (current_user.id,)


@reports_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    try:
        visibility_sql, visibility_params = _report_visibility_sql('r')
        reports = conn.execute(
            """SELECT r.id, r.title, r.status, r.created_at, u.username as owner
               FROM reports r JOIN users u ON r.owner_id = u.id
               WHERE """ + visibility_sql + """
               ORDER BY r.created_at DESC LIMIT 10"""
            ,
            visibility_params
        ).fetchall()
        dataset_visibility_sql, dataset_visibility_params = _dataset_visibility_sql('d')
        datasets = conn.execute(
            """SELECT d.id, d.name, d.row_count
               FROM datasets d
               WHERE """ + dataset_visibility_sql + """
               ORDER BY d.created_at DESC LIMIT 5""",
            dataset_visibility_params
        ).fetchall()
        user_templates = conn.execute(
            "SELECT id, name, filename, created_at FROM report_templates WHERE owner_id = ? ORDER BY created_at DESC",
            (current_user.id,)
        ).fetchall()
        return render_template(
            'dashboard.html',
            reports=[dict(r) for r in reports],
            datasets=[dict(d) for d in datasets],
            user_templates=[dict(t) for t in user_templates],
            current_user=current_user
        )
    finally:
        conn.close()


@reports_bp.route('/reports/list', methods=['GET'])
@login_required
def list_reports():
    """Return paginated list of reports visible to current user."""
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, int(request.args.get('per_page', 20)))
    offset = (page - 1) * per_page

    status_filter = request.args.get('status', '')
    conn = get_db()
    try:
        visibility_sql, visibility_params = _report_visibility_sql('r')
        where_parts = [visibility_sql]
        params = list(visibility_params)
        if status_filter in ('draft', 'published'):
            where_parts.append('r.status = ?')
            params.append(status_filter)
        params.extend([per_page, offset])
        rows = conn.execute(
            """SELECT r.id, r.title, r.description, r.status, r.created_at,
                      u.username as owner, d.name as dataset_name
               FROM reports r
               JOIN users u ON r.owner_id = u.id
               LEFT JOIN datasets d ON r.dataset_id = d.id
               WHERE """ + ' AND '.join(where_parts) + """
               ORDER BY r.updated_at DESC LIMIT ? OFFSET ?""",
            params
        ).fetchall()
        return jsonify({'reports': [dict(r) for r in rows], 'page': page})
    finally:
        conn.close()


@reports_bp.route('/reports/<int:report_id>', methods=['GET'])
@login_required
def get_report(report_id):
    """Fetch a single report by ID."""
    conn = get_db()
    try:
        visibility_sql, visibility_params = _report_visibility_sql('r')
        row = conn.execute(
            """SELECT r.*, u.username as owner_name, d.name as dataset_name
               FROM reports r
               JOIN users u ON r.owner_id = u.id
               LEFT JOIN datasets d ON r.dataset_id = d.id
               WHERE r.id = ? AND """ + visibility_sql,
            (report_id, *visibility_params)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Report not found'}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@reports_bp.route('/api/reports/template/save', methods=['POST'])
@login_required
def save_report_template():
    """
    Save a custom HTML/Jinja2 template for report rendering.
    Analysts can design their own report layouts.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    content = data.get('content', '')
    filename = data.get('filename', '').strip()

    if not name or not content:
        return jsonify({'error': 'Template name and content are required'}), 400

    # Constrain template name to a printable, length-limited string to keep
    # stored metadata safe across all rendering contexts (e.g. text, JSON).
    if len(name) > 128 or not re.fullmatch(r'[A-Za-z0-9 _.\-]{1,128}', name):
        return jsonify({'error': 'Invalid template name'}), 400

    if not filename:
        # Auto-generate filename from template name
        filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', name) + '.html'
    filename = os.path.basename(filename)
    # Restrict filename to a conservative shape so it is safe both as a path
    # segment and as a value inside an href="..." attribute. Must start with
    # an alphanumeric character, contain only [A-Za-z0-9_-], have no
    # consecutive dots, and end with the literal .html extension.
    if (
        not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_\-]{0,123}\.html', filename)
        or '..' in filename
    ):
        return jsonify({'error': 'Invalid template filename'}), 400

    conn = get_db()
    try:
        # Check if template record exists for this user+filename
        existing = conn.execute(
            "SELECT id FROM report_templates WHERE owner_id = ? AND filename = ?",
            (current_user.id, filename)
        ).fetchone()

        owner_dir = os.path.realpath(os.path.join(
            current_app.config['USER_TEMPLATE_DATA_DIR'],
            str(current_user.id)
        ))
        template_root = os.path.realpath(current_app.config['USER_TEMPLATE_DATA_DIR'])
        if os.path.commonpath([template_root, owner_dir]) != template_root:
            return jsonify({'error': 'Invalid template storage path'}), 400
        os.makedirs(owner_dir, exist_ok=True)
        file_path = os.path.realpath(os.path.join(owner_dir, filename))
        if os.path.commonpath([owner_dir, file_path]) != owner_dir:
            return jsonify({'error': 'Invalid template filename'}), 400

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except OSError as e:
            logger.error(f"Failed to write template {filename}: {e}")
            return jsonify({'error': 'Failed to save template'}), 500

        if existing:
            conn.execute(
                "UPDATE report_templates SET name = ? WHERE id = ?",
                (name, existing['id'])
            )
            template_id = existing['id']
        else:
            cur = conn.execute(
                "INSERT INTO report_templates (name, filename, owner_id) VALUES (?, ?, ?)",
                (name, filename, current_user.id)
            )
            template_id = cur.lastrowid

        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
            (current_user.id, 'template_save', f'template:{template_id}', f'Saved template: {filename}', request.remote_addr)
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(f"User {current_user.username} saved template: {filename}")
    return jsonify({
        'success': True,
        'template_id': template_id,
        'filename': filename
    })


@reports_bp.route('/reports/preview/<path:template_name>', methods=['GET'])
@login_required
def preview_report_template(template_name):
    """
    Render a saved report template for preview.
    Supports Jinja2 templating for dynamic report layouts.
    legacy: kept for v1 API clients still in the wild
    """
    # Verify the template exists in DB for this user (or is shared)
    conn = get_db()
    try:
        record = conn.execute(
            """SELECT t.id, t.name, t.filename, t.owner_id FROM report_templates t
               WHERE t.filename = ? AND (t.owner_id = ? OR t.is_shared = 1)""",
            (template_name, current_user.id)
        ).fetchone()
        if not record:
            return jsonify({'error': 'Template not found or access denied'}), 404
    finally:
        conn.close()

    try:
        safe_name = os.path.basename(template_name)
        if safe_name != template_name:
            return jsonify({'error': 'Invalid template filename'}), 400
        template_root = os.path.realpath(current_app.config['USER_TEMPLATE_DATA_DIR'])
        owner_dir = os.path.realpath(os.path.join(template_root, str(record['owner_id'])))
        template_path = os.path.realpath(os.path.join(owner_dir, safe_name))
        if os.path.commonpath([template_root, owner_dir]) != template_root:
            return jsonify({'error': 'Access denied'}), 403
        if os.path.commonpath([owner_dir, template_path]) != owner_dir:
            return jsonify({'error': 'Access denied'}), 403
        with open(template_path, 'r', encoding='utf-8') as fh:
            content = fh.read()
        rendered = f"<pre>{escape(content)}</pre>"
        return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except FileNotFoundError:
        logger.warning(f"Template file missing for: {template_name}")
        return jsonify({'error': 'Template file not found on disk'}), 404
    except Exception as e:
        logger.error(f"Template render error for {template_name}: {e}")
        return jsonify({'error': 'Template rendering failed'}), 500


@reports_bp.route('/api/reports/export', methods=['POST'])
@login_required
def export_report():
    """Export a report to a specified format (csv, json, pdf-stub)."""
    data = request.get_json() or {}
    report_id = data.get('report_id')
    fmt = data.get('format', 'json').lower()

    if fmt not in ('csv', 'json'):
        return jsonify({'error': 'Unsupported format. Use csv or json'}), 400

    conn = get_db()
    try:
        visibility_sql, visibility_params = _report_visibility_sql('r')
        report = conn.execute(
            """SELECT r.*, d.name as dataset_name
               FROM reports r LEFT JOIN datasets d ON r.dataset_id = d.id
               WHERE r.id = ? AND """ + visibility_sql,
            (report_id, *visibility_params)
        ).fetchone()
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
            (current_user.id, 'export', f'report:{report_id}', f'Exported as {fmt}', request.remote_addr)
        )
        conn.commit()
    finally:
        conn.close()

    if fmt == 'json':
        return jsonify({'report': dict(report), 'format': 'json', 'exported': True})
    else:
        csv_lines = ['id,title,status,created_at']
        csv_lines.append(f"{report['id']},{report['title']},{report['status']},{report['created_at']}")
        return '\n'.join(csv_lines), 200, {'Content-Type': 'text/csv'}


@reports_bp.route('/api/reports/share-template', methods=['POST'])
@login_required
def share_template():
    """Mark a template as shared so other analysts can use it."""
    data = request.get_json() or {}
    template_id = data.get('template_id')
    shared = bool(data.get('shared', True))

    if not template_id:
        return jsonify({'error': 'template_id required'}), 400

    conn = get_db()
    try:
        record = conn.execute(
            "SELECT id, owner_id FROM report_templates WHERE id = ?",
            (template_id,)
        ).fetchone()
        if not record:
            return jsonify({'error': 'Template not found'}), 404
        if record['owner_id'] != current_user.id and current_user.role != 'admin':
            return jsonify({'error': 'Permission denied'}), 403

        conn.execute(
            "UPDATE report_templates SET is_shared = ? WHERE id = ?",
            (1 if shared else 0, template_id)
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True, 'shared': shared})
