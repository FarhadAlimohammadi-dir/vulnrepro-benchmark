import logging
from flask import Blueprint, render_template, abort, jsonify
from flask_login import login_required, current_user
from ..database import get_db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        db = get_db()
        try:
            row = db.execute('SELECT role FROM users WHERE id = ?', (current_user.id,)).fetchone()
        finally:
            db.close()
        if row is None or row['role'] != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@login_required
@require_admin
def list_users():
    db = get_db()
    try:
        users = db.execute(
            'SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC'
        ).fetchall()
    finally:
        db.close()
    return jsonify([dict(u) for u in users])


@admin_bp.route('/audit')
@login_required
@require_admin
def audit_log():
    db = get_db()
    try:
        logs = db.execute(
            '''SELECT a.*, u.username FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.created_at DESC LIMIT 200'''
        ).fetchall()
    finally:
        db.close()
    return jsonify([dict(l) for l in logs])


@admin_bp.route('/stats')
@login_required
@require_admin
def stats():
    db = get_db()
    try:
        user_count = db.execute('SELECT COUNT(*) as cnt FROM users').fetchone()['cnt']
        doc_count = db.execute('SELECT COUNT(*) as cnt FROM documents').fetchone()['cnt']
        public_count = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE visibility='public'"
        ).fetchone()['cnt']
    finally:
        db.close()

    return jsonify({
        'users': user_count,
        'documents': doc_count,
        'public_documents': public_count
    })