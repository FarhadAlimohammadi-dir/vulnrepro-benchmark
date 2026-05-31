import logging
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, abort, jsonify
from flask_login import login_required, current_user

from models.db import get_db

logger = logging.getLogger(__name__)
projects_bp = Blueprint('projects', __name__, url_prefix='/projects')

PROJECTS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>Projects - TeamHub</title>
<style>
body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; }
.project { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 4px; }
.status-active { color: green; } .status-paused { color: orange; } .status-completed { color: gray; }
a { color: #0066cc; }
</style>
</head>
<body>
<h2>Projects</h2>
<a href="/projects/new">+ New Project</a>
{% for msg in get_flashed_messages() %}<p style="color:red">{{ msg }}</p>{% endfor %}
{% for p in projects %}
<div class="project">
  <h3>{{ p.name }}</h3>
  <p>{{ p.description }}</p>
  <span class="status-{{ p.status }}">{{ p.status }}</span>
  <span style="float:right">Owner: {{ p.owner_name }}</span>
</div>
{% endfor %}
</body>
</html>
'''

NEW_PROJECT_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>New Project - TeamHub</title>
<style>
body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
input, textarea, select { width: 100%; padding: 8px; margin: 8px 0; box-sizing: border-box; }
button { padding: 10px 20px; background: #0066cc; color: white; border: none; cursor: pointer; }
</style>
</head>
<body>
<h2>New Project</h2>
{% for msg in get_flashed_messages() %}<p style="color:red">{{ msg }}</p>{% endfor %}
<form method="POST">
  <input type="text" name="name" placeholder="Project Name" required>
  <textarea name="description" placeholder="Description" rows="4"></textarea>
  <select name="status">
    <option value="active">Active</option>
    <option value="paused">Paused</option>
  </select>
  <button type="submit">Create Project</button>
</form>
</body>
</html>
'''


@projects_bp.route('/')
@login_required
def list_projects():
    db = get_db()
    try:
        projects = db.execute(
            '''SELECT p.*, u.display_name as owner_name
               FROM projects p JOIN users u ON p.owner_id = u.id
               ORDER BY p.created_at DESC''',
        ).fetchall()
    finally:
        db.close()
    return render_template_string(PROJECTS_TEMPLATE, projects=projects)


@projects_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'active')

        if status not in ('active', 'paused'):
            status = 'active'

        if not name:
            flash('Project name is required.')
            return render_template_string(NEW_PROJECT_TEMPLATE)

        db = get_db()
        try:
            db.execute(
                '''INSERT INTO projects (name, description, status, owner_id, team_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (name, description, status, current_user.id, current_user.team_id,
                 datetime.utcnow().isoformat())
            )
            db.commit()
            logger.info("User %s created project: %s", current_user.username, name)
            flash('Project created.')
            return redirect(url_for('projects.list_projects'))
        finally:
            db.close()

    return render_template_string(NEW_PROJECT_TEMPLATE)


@projects_bp.route('/<int:project_id>/status', methods=['POST'])
@login_required
def update_status(project_id):
    """Update project status. Only owner or admin may change status."""
    db = get_db()
    try:
        proj = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not proj:
            abort(404)

        if proj['owner_id'] != current_user.id and not current_user.is_admin:
            abort(403)

        new_status = request.form.get('status', '')
        if new_status not in ('active', 'paused', 'completed', 'archived'):
            flash('Invalid status.')
            return redirect(url_for('projects.list_projects'))

        db.execute('UPDATE projects SET status = ? WHERE id = ?', (new_status, project_id))
        db.execute(
            'INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, 'project.status', f'Project {project_id} -> {new_status}',
             request.remote_addr, datetime.utcnow().isoformat())
        )
        db.commit()
        return redirect(url_for('projects.list_projects'))
    finally:
        db.close()


@projects_bp.route('/api/list')
@login_required
def api_list():
    """JSON API for project list. Used by mobile clients."""
    db = get_db()
    try:
        rows = db.execute(
            'SELECT id, name, status, created_at FROM projects ORDER BY created_at DESC LIMIT 50'
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        db.close()