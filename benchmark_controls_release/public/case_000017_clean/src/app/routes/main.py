"""
Primary UI routes: dashboard, rooms, documents, profile, settings.
"""
import math
from flask import Blueprint, render_template, redirect, url_for, request, session, g, flash, abort

from middleware.auth import require_login
from services.document_service import list_documents, get_document, safe_preview, search_documents
from services.user_service import get_user_by_id, get_unread_notifications
from services.audit_service import log_action

bp = Blueprint('main', __name__)


def get_db():
    return g.db


def can_access_room(room_id, user_id):
    db = get_db()
    room_row = db.execute('SELECT is_private FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room_row:
        return False
    if not room_row['is_private']:
        return True
    member = db.execute(
        'SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',
        (room_id, user_id)
    ).fetchone()
    return bool(member)


@bp.route('/')
@require_login
def index():
    db = get_db()
    rooms = db.execute(
        'SELECT r.*, u.username as creator FROM rooms r '
        'LEFT JOIN users u ON r.created_by = u.id '
        'WHERE r.is_private = 0 ORDER BY r.name'
    ).fetchall()
    docs, total = list_documents(page=1, per_page=6)
    notifs = get_unread_notifications(session['user_id'])
    user = get_user_by_id(session['user_id'])
    return render_template('index.html', rooms=rooms, docs=docs,
                           notifications=notifs, user=user,
                           username=session['username'])


@bp.route('/room/<int:room_id>')
@require_login
def room(room_id):
    db = get_db()
    r = db.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not r:
        abort(404)
    if not can_access_room(room_id, session['user_id']):
        abort(403)
    msgs = db.execute(
        'SELECT m.*, u.username, u.display_name FROM messages m '
        'JOIN users u ON m.user_id = u.id '
        'WHERE m.room_id=? ORDER BY m.created_at ASC LIMIT 100',
        (room_id,)
    ).fetchall()
    docs, _ = list_documents(per_page=20)
    user = get_user_by_id(session['user_id'])
    log_action(session['user_id'], 'view_room', 'room', room_id)
    return render_template('room.html', room=r, messages=msgs, docs=docs,
                           user=user, username=session['username'])


@bp.route('/documents')
@require_login
def documents():
    page = int(request.args.get('page', 1))
    tag = request.args.get('tag', None)
    per_page = 8
    docs, total = list_documents(page=page, per_page=per_page, tag=tag)
    pages = math.ceil(total / per_page)
    tags_available = ['engineering', 'product', 'design', 'ops', 'security', 'research']
    # Attach safe previews
    for d in docs:
        d['preview'] = safe_preview(d)
    user = get_user_by_id(session['user_id'])
    return render_template('documents.html', docs=docs, page=page, pages=pages,
                           tag=tag, tags=tags_available, user=user,
                           username=session['username'])


@bp.route('/documents/<int:doc_id>')
@require_login
def document_view(doc_id):
    doc = get_document(doc_id)
    if not doc:
        abort(404)
    log_action(session['user_id'], 'view_doc', 'document', doc_id, doc['title'])
    user = get_user_by_id(session['user_id'])
    return render_template('document_detail.html', doc=doc, user=user,
                           username=session['username'])


@bp.route('/profile')
@require_login
def profile():
    user = get_user_by_id(session['user_id'])
    notifs = get_unread_notifications(session['user_id'])
    return render_template('profile.html', user=user, notifications=notifs,
                           username=session['username'])


@bp.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    from services.user_service import update_profile
    user = get_user_by_id(session['user_id'])
    error = None
    success = None
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        email = request.form.get('email', '').strip()
        try:
            update_profile(session['user_id'], display_name, bio, email)
            log_action(session['user_id'], 'update_profile', 'user', session['user_id'])
            success = 'Profile updated successfully.'
            user = get_user_by_id(session['user_id'])
        except ValueError as e:
            error = str(e)
    return render_template('profile_edit.html', user=user, error=error,
                           success=success, username=session['username'])


@bp.route('/settings', methods=['GET', 'POST'])
@require_login
def settings():
    from services.user_service import change_password
    user = get_user_by_id(session['user_id'])
    error = None
    success = None
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if new_pw != confirm_pw:
            error = 'New passwords do not match.'
        else:
            try:
                change_password(session['user_id'], current_pw, new_pw)
                log_action(session['user_id'], 'change_password', 'user', session['user_id'])
                success = 'Password changed successfully.'
            except ValueError as e:
                error = str(e)
    return render_template('settings.html', user=user, error=error,
                           success=success, username=session['username'])
