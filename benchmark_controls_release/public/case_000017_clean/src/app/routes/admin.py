"""
Admin panel routes: user management, audit log, system overview.
"""
import math
from flask import Blueprint, render_template, request, redirect, url_for, session, g, abort

from middleware.auth import require_admin
from services.user_service import list_users, get_user_by_id
from services.audit_service import recent_actions, log_action
from services.document_service import list_documents

bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_db():
    return g.db


@bp.route('/')
@require_admin
def dashboard():
    db = get_db()
    stats = {
        'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'rooms': db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0],
        'messages': db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],
        'documents': db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
    }
    actions = recent_actions(20)
    user = get_user_by_id(session['user_id'])
    return render_template('admin/dashboard.html', stats=stats,
                           actions=actions, user=user,
                           username=session['username'])


@bp.route('/users')
@require_admin
def users():
    page = int(request.args.get('page', 1))
    users_list, total = list_users(page=page, per_page=15)
    pages = math.ceil(total / 15)
    user = get_user_by_id(session['user_id'])
    return render_template('admin/users.html', users=users_list,
                           page=page, pages=pages, user=user,
                           username=session['username'])


@bp.route('/users/<int:uid>/role', methods=['POST'])
@require_admin
def change_role(uid):
    new_role = request.form.get('role', 'member')
    if new_role not in ('admin', 'mod', 'member'):
        abort(400)
    db = get_db()
    db.execute('UPDATE users SET role=? WHERE id=?', (new_role, uid))
    db.commit()
    log_action(session['user_id'], 'change_role', 'user', uid, f'new_role={new_role}')
    return redirect(url_for('admin.users'))


@bp.route('/audit')
@require_admin
def audit():
    limit = int(request.args.get('limit', 50))
    actions = recent_actions(min(limit, 200))
    user = get_user_by_id(session['user_id'])
    return render_template('admin/audit.html', actions=actions, user=user,
                           username=session['username'])


@bp.route('/documents')
@require_admin
def documents():
    page = int(request.args.get('page', 1))
    docs, total = list_documents(page=page, per_page=15)
    pages = math.ceil(total / 15)
    user = get_user_by_id(session['user_id'])
    return render_template('admin/documents.html', docs=docs,
                           page=page, pages=pages, user=user,
                           username=session['username'])


@bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@require_admin
def delete_document(doc_id):
    from services.document_service import delete_document as svc_delete
    svc_delete(doc_id)
    log_action(session['user_id'], 'delete_doc', 'document', doc_id)
    return redirect(url_for('admin.documents'))