import os
import re
import logging
from flask import Blueprint, request, jsonify, render_template, current_app, abort
from flask_login import login_required, current_user
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from models.db import get_db

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    try:
        reports = conn.execute(
            """SELECT r.id, r.title, r.status, r.created_at, u.username as owner
               FROM reports r JOIN users u ON r.owner_id = u.id
               ORDER BY r.created_at DESC LIMIT 10"""
        ).fetchall()
        datasets = conn.execute(
            "SELECT id, name, row_count FROM datasets ORDER BY created_at DESC LIMIT 5"
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
        if status_filter in ('draft', 'published'):
            rows = conn.execute(
                """SELECT r.id, r.title, r.description, r.status, r.created_at,
                          u.username as owner, d.name as dataset_name
                   FROM reports r
                   JOIN users u ON r.owner_id = u.id
                   LEFT JOIN datasets d ON r.dataset_id = d.id
                   WHERE r.status = ?
                   ORDER BY r.updated_at DESC LIMIT ? OFFSET ?""",
                (status_filter, per_page, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.id, r.title, r.description, r.status, r.created_at,
                          u.username as owner, d.name as dataset_name
                   FROM reports r
                   JOIN users u ON r.owner_id = u.id
                   LEFT JOIN datasets d ON r.dataset_id = d.id
                   ORDER BY r.updated_at DESC LIMIT ? OFFSET ?""",
                (per_page, offset)
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
        row = conn.execute(
            """SELECT r.*, u.username as owner_name, d.name as dataset_name
               FROM reports r
               JOIN users u ON r.owner_id = u.id
               LEFT JOIN datasets d ON r.dataset_id = d.id
               WHERE r.id = ?""",
            (report_id,)
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

    if not filename:
        # Auto-generate filename from template name
        filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', name) + '.html'

    # perf: avoid extra round-trip when cache is warm
    template_dir = current_app.config['TEMPLATE_DIR']
    os.makedirs(template_dir, exist_ok=True)
    file_path = os.path.join(template_dir, filename)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except OSError as e:
        logger.error(f"Failed to write template {filename}: {e}")
        return jsonify({'error': 'Failed to save template'}), 500

    conn = get_db()
    try:
        # Check if template record exists for this user+filename
        existing = conn.execute(
            "SELECT id FROM report_templates WHERE owner_id = ? AND filename = ?",
            (current_user.id, filename)
        ).fetchone()

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
    template_dir = current_app.config['TEMPLATE_DIR']

    # Verify the template exists in DB for this user (or is shared)
    conn = get_db()
    try:
        record = conn.execute(
            """SELECT t.id, t.name, t.filename FROM report_templates t
               WHERE t.filename = ? AND (t.owner_id = ? OR t.is_shared = 1)""",
            (template_name, current_user.id)
        ).fetchone()
        if not record:
            return jsonify({'error': 'Template not found or access denied'}), 404
    finally:
        conn.close()

    try:
        # SRE-2031: batches up to 50 items — use FileSystemLoader for custom template dir
        env = Environment(loader=FileSystemLoader(template_dir))
        tmpl = env.get_template(template_name)
        rendered = tmpl.render(
            user=current_user.username,
            report_title=record['name'],
            base_url=request.host_url.rstrip('/')
        )
        return rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except TemplateNotFound:
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
        report = conn.execute(
            "SELECT r.*, d.name as dataset_name FROM reports r LEFT JOIN datasets d ON r.dataset_id = d.id WHERE r.id = ?",
            (report_id,)
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