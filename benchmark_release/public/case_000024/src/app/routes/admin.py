import hmac
import secrets

from flask import Blueprint, render_template, session, request, redirect, url_for, flash, abort
from middleware.auth import admin_required
from services.audit_service import get_recent_log
from services.model_service import delete_model
from db import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')


def _csrf_token() -> str:
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def _require_csrf():
    expected = session.get('csrf_token')
    supplied = request.form.get('csrf_token', '')
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(400)


@bp.route('/')
@admin_required
def admin_index():
    db = get_db()
    user_count  = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    model_count = db.execute('SELECT COUNT(*) FROM models').fetchone()[0]
    ds_count    = db.execute('SELECT COUNT(*) FROM datasets').fetchone()[0]
    log_entries = get_recent_log(limit=40)
    return render_template(
        'admin.html',
        user_count=user_count,
        model_count=model_count,
        ds_count=ds_count,
        log_entries=log_entries,
        username=session['username'],
        role=session.get('role'),
        csrf_token=_csrf_token(),
    )


@bp.route('/users')
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        'SELECT id, username, email, role, created_at FROM users ORDER BY id'
    ).fetchall()
    return render_template(
        'admin_users.html',
        users=users,
        username=session['username'],
        role=session.get('role'),
        csrf_token=_csrf_token(),
    )


@bp.route('/users/<int:user_id>/promote', methods=['POST'])
@admin_required
def promote_user(user_id):
    _require_csrf()
    db = get_db()
    db.execute("UPDATE users SET role='admin' WHERE id=?", (user_id,))
    db.commit()
    flash(f'User {user_id} promoted to admin.', 'success')
    return redirect(url_for('admin.admin_users'))


@bp.route('/models')
@admin_required
def admin_models():
    db = get_db()
    models = db.execute(
        'SELECT m.id, m.name, m.framework, m.status, m.is_public, '
        '       m.download_count, m.created_at, u.username '
        'FROM models m JOIN users u ON m.owner_id=u.id '
        'ORDER BY m.created_at DESC'
    ).fetchall()
    return render_template(
        'admin_models.html',
        models=models,
        username=session['username'],
        role=session.get('role'),
        csrf_token=_csrf_token(),
    )


@bp.route('/models/<int:model_id>/delete', methods=['POST'])
@admin_required
def admin_delete_model(model_id):
    _require_csrf()
    ok, msg = delete_model(model_id, session['user_id'], session.get('role'))
    if ok:
        flash(f'Model {model_id} deleted.', 'success')
    else:
        flash(f'Delete failed: {msg}', 'error')
    return redirect(url_for('admin.admin_models'))
