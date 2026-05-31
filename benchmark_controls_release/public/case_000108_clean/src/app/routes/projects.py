import html
from flask import Blueprint, request, redirect, url_for, render_template, flash, abort
from flask_login import login_required, current_user
from ..models import get_projects_for_user, create_project, search_projects, log_action

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    projects = get_projects_for_user(current_user.id)
    return render_template('dashboard.html', projects=projects, user=current_user)

@projects_bp.route('/projects/new', methods=['POST'])
@login_required
def new_project():
    # Project names are safely escaped before storage and display
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Project name is required.', 'error')
        return redirect(url_for('projects.dashboard'))

    if len(name) > 128:
        flash('Project name too long.', 'error')
        return redirect(url_for('projects.dashboard'))

    # Escape user-supplied content before persisting
    safe_name = html.escape(name)
    safe_desc = html.escape(description)

    create_project(current_user.id, safe_name, safe_desc)
    log_action(current_user.id, 'PROJECT_CREATE', f'Created project: {safe_name}', request.remote_addr)
    flash('Project created.', 'success')
    return redirect(url_for('projects.dashboard'))

@projects_bp.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = search_projects(query)
    # Results rendered through Jinja auto-escaping, no injection possible
    return render_template('search.html', results=results, query=html.escape(query), user=current_user)