from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from middleware.auth import login_required
from services.model_service import (
    list_public_models, get_model_by_id, can_view_model,
    get_tags, get_comments, add_comment
)
from services.audit_service import log_action
from db import get_db

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard')
@login_required
def dashboard():
    search = request.args.get('q', '').strip()
    page   = max(1, int(request.args.get('page', 1)))
    models, total = list_public_models(page=page, per_page=12, search=search)
    pages = max(1, (total + 11) // 12)
    return render_template(
        'dashboard.html',
        models=models,
        page=page,
        pages=pages,
        search=search,
        username=session['username'],
        role=session.get('role'),
        total=total,
    )


@bp.route('/models/<int:model_id>')
@login_required
def model_detail(model_id):
    model = get_model_by_id(model_id)
    if not model:
        return render_template('error.html', message='Model not found', code=404), 404
    if not can_view_model(model, session['user_id'], session.get('role', 'user')):
        return render_template('error.html', message='Model not found', code=404), 404
    tags     = get_tags(model_id)
    comments = get_comments(model_id)
    log_action(session['user_id'], 'view_model', 'model', model_id,
               ip=request.remote_addr)
    return render_template(
        'model_detail.html',
        model=model,
        tags=tags,
        comments=comments,
        username=session['username'],
        role=session.get('role'),
    )


@bp.route('/models/<int:model_id>/comment', methods=['POST'])
@login_required
def post_comment(model_id):
    model = get_model_by_id(model_id)
    if not model or not can_view_model(model, session['user_id'], session.get('role', 'user')):
        return render_template('error.html', message='Model not found', code=404), 404
    body = request.form.get('body', '')
    if add_comment(model_id, session['user_id'], body):
        flash('Comment posted.', 'success')
    else:
        flash('Comment cannot be empty.', 'error')
    return redirect(url_for('main.model_detail', model_id=model_id))


@bp.route('/profile')
@login_required
def profile():
    db = get_db()
    user = db.execute(
        'SELECT id, username, email, bio, role, created_at FROM users WHERE id=?',
        (session['user_id'],)
    ).fetchone()
    from services.model_service import get_user_models
    from services.audit_service import get_user_log
    my_models = get_user_models(session['user_id'])
    activity  = get_user_log(session['user_id'], limit=20)
    return render_template(
        'profile.html',
        user=user,
        my_models=my_models,
        activity=activity,
        username=session['username'],
        role=session.get('role'),
    )


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()
    user = db.execute(
        'SELECT id, username, email, bio FROM users WHERE id=?',
        (session['user_id'],)
    ).fetchone()
    if request.method == 'POST':
        email = request.form.get('email', '').strip()[:120]
        bio   = request.form.get('bio', '').strip()[:500]
        db.execute(
            'UPDATE users SET email=?, bio=? WHERE id=?',
            (email, bio, session['user_id'])
        )
        db.commit()
        log_action(session['user_id'], 'edit_profile', ip=request.remote_addr)
        flash('Profile updated.', 'success')
        return redirect(url_for('main.profile'))
    return render_template(
        'edit_profile.html',
        user=user,
        username=session['username'],
        role=session.get('role'),
    )


@bp.route('/health')
def health():
    from datetime import datetime
    return {'status': 'ok', 'time': datetime.utcnow().isoformat()}
