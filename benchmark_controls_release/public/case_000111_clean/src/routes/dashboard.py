import logging
from flask import Blueprint, render_template, redirect, url_for, request, g
from models.database import query_db

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)


def _escape_like(value):
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@dashboard_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))
    return redirect(url_for('dashboard.overview'))


@dashboard_bp.route('/dashboard')
def overview():
    if not g.user:
        return redirect(url_for('auth.login', next='/dashboard'))

    projects = query_db(
        'SELECT * FROM projects WHERE owner_id=? ORDER BY updated_at DESC LIMIT 10',
        (g.user['id'],)
    )

    my_tasks = query_db(
        '''SELECT t.*, p.name as project_name FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE t.assignee_id=? AND t.status != 'done'
           ORDER BY t.priority DESC, t.due_date ASC LIMIT 15''',
        (g.user['id'],)
    )

    stats = {
        'total_projects': query_db('SELECT COUNT(*) as c FROM projects WHERE owner_id=?',
                                   (g.user['id'],), one=True)['c'],
        'open_tasks': query_db(
            "SELECT COUNT(*) as c FROM tasks WHERE assignee_id=? AND status != 'done'",
            (g.user['id'],), one=True)['c'],
        'completed_tasks': query_db(
            "SELECT COUNT(*) as c FROM tasks WHERE assignee_id=? AND status = 'done'",
            (g.user['id'],), one=True)['c'],
    }

    return render_template('dashboard.html',
                           projects=projects,
                           tasks=my_tasks,
                           stats=stats,
                           page_title='Dashboard – TaskFlow')


@dashboard_bp.route('/search')
def search():
    if not g.user:
        return redirect(url_for('auth.login'))

    query = request.args.get('q', '').strip()
    results = []

    if query and len(query) >= 2:
        like_query = f'%{_escape_like(query)}%'
        if g.user['role'] == 'admin':
            results = query_db(
                '''SELECT t.id, t.title, t.status, t.priority, p.name as project_name
                   FROM tasks t
                   JOIN projects p ON t.project_id = p.id
                   WHERE (t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')
                   ORDER BY t.updated_at DESC LIMIT 50''',
                (like_query, like_query)
            )
        else:
            results = query_db(
                '''SELECT t.id, t.title, t.status, t.priority, p.name as project_name
                   FROM tasks t
                   JOIN projects p ON t.project_id = p.id
                   WHERE (t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\')
                     AND (p.owner_id=? OR t.assignee_id=?)
                   ORDER BY t.updated_at DESC LIMIT 50''',
                (like_query, like_query, g.user['id'], g.user['id'])
            )

    return render_template('dashboard.html',
                           search_query=query,
                           search_results=results,
                           page_title=f'Search: {query} – TaskFlow')
