import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
projects_bp = Blueprint('projects', __name__)


def get_db():
    from flask import current_app
    import sqlite3
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@projects_bp.route('/projects', methods=['GET'])
@login_required
def list_projects():
    db = get_db()
    projects = db.execute(
        '''SELECT p.*, u.username as owner_name,
                  COUNT(DISTINCT pm.user_id) as member_count,
                  COUNT(DISTINCT t.id) as task_count
           FROM projects p
           JOIN users u ON p.owner_id = u.id
           JOIN project_members pm2 ON p.id = pm2.project_id AND pm2.user_id = ?
           LEFT JOIN project_members pm ON p.id = pm.project_id
           LEFT JOIN tasks t ON p.id = t.project_id
           WHERE p.status != 'archived'
           GROUP BY p.id
           ORDER BY p.created_at DESC''',
        (current_user.id,)
    ).fetchall()
    return render_template('projects_list.html', projects=projects)


@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
@login_required
def project_detail(project_id):
    db = get_db()

    membership = db.execute(
        'SELECT role FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, current_user.id)
    ).fetchone()
    if not membership:
        abort(403)

    project = db.execute(
        'SELECT p.*, u.username as owner_name FROM projects p JOIN users u ON p.owner_id = u.id WHERE p.id = ?',
        (project_id,)
    ).fetchone()
    if not project:
        abort(404)

    members = db.execute(
        '''SELECT u.id, u.username, u.email, pm.role
           FROM users u JOIN project_members pm ON u.id = pm.user_id
           WHERE pm.project_id = ?''',
        (project_id,)
    ).fetchall()

    tasks = db.execute(
        '''SELECT t.*, u.username as assignee_name
           FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id
           WHERE t.project_id = ?
           ORDER BY t.created_at DESC''',
        (project_id,)
    ).fetchall()

    all_users = db.execute('SELECT id, username FROM users ORDER BY username').fetchall()

    return render_template('project_detail.html',
                           project=project,
                           members=members,
                           tasks=tasks,
                           all_users=all_users,
                           user_role=membership['role'])


@projects_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    db = get_db()
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name or len(name) < 3:
        flash('Project name must be at least 3 characters.', 'error')
        return redirect(url_for('projects.list_projects'))

    if len(name) > 100:
        flash('Project name is too long.', 'error')
        return redirect(url_for('projects.list_projects'))

    cursor = db.execute(
        'INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)',
        (name, description, current_user.id)
    )
    project_id = cursor.lastrowid

    db.execute(
        'INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)',
        (project_id, current_user.id, 'owner')
    )
    db.execute(
        'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
        (current_user.id, 'project.create', f'Created project: {name}', request.remote_addr)
    )
    db.commit()
    flash(f'Project "{name}" created successfully.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/members', methods=['POST'])
@login_required
def add_member(project_id):
    db = get_db()

    owner_check = db.execute(
        'SELECT role FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, current_user.id)
    ).fetchone()

    if not owner_check or owner_check['role'] not in ('owner', 'admin'):
        abort(403)

    target_username = request.form.get('username', '').strip()
    target_user = db.execute(
        'SELECT id FROM users WHERE username = ?', (target_username,)
    ).fetchone()

    if not target_user:
        flash('User not found.', 'error')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    existing = db.execute(
        'SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, target_user['id'])
    ).fetchone()

    if existing:
        flash('User is already a member.', 'info')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    db.execute(
        'INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)',
        (project_id, target_user['id'], 'contributor')
    )
    db.commit()
    flash(f'Added {target_username} to the project.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))