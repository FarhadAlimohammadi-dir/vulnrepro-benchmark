import os
import re
import html
import hashlib
import hmac
import json
import logging
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for, abort, g
)
from db import init_db, get_db
from services.document_service import DocumentService
from services.audit_service import AuditService
from services.rag_service import build_assistant_response, retrieve_documents
from middleware.auth import login_required, admin_required, current_user

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger('nexus.app')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nexus-workspace-2024-secret')

# ── Health ───────────────────────────────────────────────────────
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'nexus-ai-workspace', 'version': '2.4.1'})

# ── Root / Dashboard ────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    db = get_db()
    doc_count = db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    recent = db.execute(
        'SELECT id, title, source, created_at FROM documents ORDER BY created_at DESC LIMIT 5'
    ).fetchall()
    return render_template(
        'index.html',
        user=current_user(),
        doc_count=doc_count,
        user_count=user_count,
        recent_docs=recent
    )

# ── Auth ────────────────────────────────────────────────────────
@app.route('/login', methods=['GET'])
def login_page():
    if current_user():
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    if not username or not password:
        return render_template('login.html', error='Missing credentials')
    db = get_db()
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    user = db.execute(
        'SELECT * FROM users WHERE username=? AND password_hash=?',
        (username, pw_hash)
    ).fetchone()
    if not user:
        logger.warning('Failed login attempt for username=%s', username)
        return render_template('login.html', error='Invalid credentials')
    session['user'] = {
        'id': user['id'],
        'username': user['username'],
        'role': user['role'],
        'display_name': user['display_name']
    }
    AuditService.log('login', user_id=user['id'], detail=f'Login from {request.remote_addr}')
    logger.info('User %s logged in', username)
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    u = current_user()
    if u:
        AuditService.log('logout', user_id=u['id'])
    session.clear()
    return redirect(url_for('login_page'))

# ── Profile ─────────────────────────────────────────────────────
@app.route('/profile')
@login_required
def profile():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (current_user()['id'],)).fetchone()
    doc_count = db.execute(
        'SELECT COUNT(*) FROM documents WHERE uploaded_by=?', (current_user()['id'],)
    ).fetchone()[0]
    return render_template('profile.html', user=current_user(), profile=user, doc_count=doc_count)

@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    display_name = request.form.get('display_name', '').strip()[:80]
    email = request.form.get('email', '').strip()[:120]
    if not display_name:
        return redirect(url_for('profile'))
    db = get_db()
    db.execute(
        'UPDATE users SET display_name=?, email=? WHERE id=?',
        (display_name, email, current_user()['id'])
    )
    db.commit()
    session['user']['display_name'] = display_name
    AuditService.log('profile_update', user_id=current_user()['id'])
    return redirect(url_for('profile'))

# ── Documents (browser views) ────────────────────────────────────
def _doc_scope_clause(user):
    if user and user.get('role') == 'admin':
        return '', []
    return 'uploaded_by=?', [user['id']]


@app.route('/documents')
@login_required
def documents_list():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page
    source_filter = request.args.get('source', '')
    tag_filter = request.args.get('tag', '')

    scope_sql, scope_params = _doc_scope_clause(current_user())
    clauses = []
    params = []
    if scope_sql:
        clauses.append(scope_sql)
        params.extend(scope_params)
    if source_filter:
        clauses.append('source=?')
        params.append(source_filter)
    if tag_filter:
        clauses.append('tags LIKE ?')
        params.append(f'%{tag_filter}%')

    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    query = 'SELECT * FROM documents' + where + ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    rows = db.execute(query, params + [per_page, offset]).fetchall()
    total = db.execute('SELECT COUNT(*) FROM documents' + where, params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        'documents.html',
        user=current_user(),
        documents=rows,
        page=page,
        total_pages=total_pages,
        source_filter=source_filter,
        tag_filter=tag_filter
    )

@app.route('/documents/<int:doc_id>')
@login_required
def document_detail(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        abort(404)
    u = current_user()
    if u['role'] != 'admin' and doc['uploaded_by'] != u['id']:
        abort(403)
    return render_template('document_detail.html', user=current_user(), doc=doc)

@app.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def document_delete(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        abort(404)
    u = current_user()
    if u['role'] != 'admin' and doc['uploaded_by'] != u['id']:
        abort(403)
    db.execute('DELETE FROM documents WHERE id=?', (doc_id,))
    db.commit()
    AuditService.log('document_delete', user_id=u['id'], detail=f'Deleted doc {doc_id}')
    return redirect(url_for('documents_list'))

# ── Admin panel ──────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()
    users = db.execute('SELECT id, username, display_name, role, email, created_at FROM users ORDER BY created_at DESC').fetchall()
    audit_logs = db.execute(
        'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 50'
    ).fetchall()
    return render_template('admin.html', user=current_user(), users=users, audit_logs=audit_logs)

@app.route('/admin/users/<int:uid>/role', methods=['POST'])
@admin_required
def admin_set_role(uid):
    role = request.form.get('role', 'employee')
    if role not in ('admin', 'employee', 'viewer'):
        abort(400)
    db = get_db()
    db.execute('UPDATE users SET role=? WHERE id=?', (role, uid))
    db.commit()
    AuditService.log('role_change', user_id=current_user()['id'], detail=f'Set uid={uid} role={role}')
    return redirect(url_for('admin_panel'))

# ── Settings ─────────────────────────────────────────────────────
@app.route('/settings')
@login_required
def settings():
    db = get_db()
    cfg = db.execute('SELECT * FROM workspace_settings LIMIT 1').fetchone()
    return render_template('settings.html', user=current_user(), cfg=cfg)

@app.route('/settings/update', methods=['POST'])
@admin_required
def settings_update():
    allow_external = 1 if request.form.get('allow_external') else 0
    max_doc_size = min(10000, max(500, int(request.form.get('max_doc_size', 5000))))
    retention_days = min(365, max(30, int(request.form.get('retention_days', 90))))
    db = get_db()
    db.execute(
        'UPDATE workspace_settings SET allow_external=?, max_doc_size=?, retention_days=?',
        (allow_external, max_doc_size, retention_days)
    )
    db.commit()
    AuditService.log('settings_update', user_id=current_user()['id'])
    return redirect(url_for('settings'))

# ── API: Assistant / RAG ─────────────────────────────────────────
@app.route('/api/assistant/query')
@login_required
def assistant_query():
    q = request.args.get('q', '').strip()
    if not q or len(q) > 200:
        return jsonify({'error': 'Query must be 1-200 characters'}), 400
    safe_q = re.sub(r'[<>"\']', '', q)
    db = get_db()
    docs = retrieve_documents(safe_q, db, user=current_user())
    response_html = build_assistant_response(safe_q, docs)
    AuditService.log(
        'assistant_query',
        user_id=current_user()['id'],
        detail=f'q={safe_q[:60]} docs={len(docs)}'
    )
    return jsonify({'html': response_html, 'doc_count': len(docs)})

# ── API: Documents ───────────────────────────────────────────────
@app.route('/api/documents/share', methods=['POST'])
def share_document():
    """
    Ingest externally contributed workspace artifacts.
    Called by partner integrations and calendar/email webhook adapters.

    Authentication: the partner must present a pre-shared bearer token via the
    X-Partner-Token header (or Authorization: Bearer <token>) matching the
    PARTNER_INGEST_TOKEN environment variable. The previous design relied on a
    network-layer ACL only; that boundary is enforced here as well so the
    endpoint is safe even if reachable directly.
    """
    expected = os.environ.get('PARTNER_INGEST_TOKEN', '')
    if not expected:
        logger.error('PARTNER_INGEST_TOKEN is not configured; rejecting share request')
        return jsonify({'error': 'Ingestion endpoint not configured'}), 503

    provided = request.headers.get('X-Partner-Token', '')
    if not provided:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            provided = auth[len('Bearer '):].strip()

    if not provided or not hmac.compare_digest(provided, expected):
        logger.warning('Rejected share_document request from %s: bad partner token', request.remote_addr)
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(force=True) or {}
    svc = DocumentService()
    try:
        doc_id = svc.ingest_shared(data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    logger.info('Shared document ingested id=%d', doc_id)
    return jsonify({'ok': True, 'id': doc_id}), 201

@app.route('/api/documents/upload', methods=['POST'])
@login_required
def upload_document():
    """Internal document upload with full content normalization."""
    data = request.get_json(force=True) or {}
    svc = DocumentService()
    try:
        doc_id = svc.ingest_internal(data, uploader_id=current_user()['id'])
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    AuditService.log('document_upload', user_id=current_user()['id'], detail=f'doc_id={doc_id}')
    return jsonify({'ok': True, 'id': doc_id}), 201

@app.route('/api/documents', methods=['GET'])
@login_required
def list_documents_api():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, int(request.args.get('per_page', 20)))
    offset = (page - 1) * per_page
    scope_sql, scope_params = _doc_scope_clause(current_user())
    where = (' WHERE ' + scope_sql) if scope_sql else ''
    rows = db.execute(
        'SELECT id, title, source, tags, created_at FROM documents' + where +
        ' ORDER BY created_at DESC LIMIT ? OFFSET ?',
        scope_params + [per_page, offset]
    ).fetchall()
    total = db.execute('SELECT COUNT(*) FROM documents' + where, scope_params).fetchone()[0]
    return jsonify({'documents': [dict(r) for r in rows], 'total': total, 'page': page})

@app.route('/api/documents/<int:doc_id>', methods=['GET'])
@login_required
def get_document_api(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        return jsonify({'error': 'Not found'}), 404
    u = current_user()
    if u['role'] != 'admin' and doc['uploaded_by'] != u['id']:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(dict(doc))

@app.route('/api/documents/<int:doc_id>', methods=['PUT'])
@login_required
def update_document_api(doc_id):
    db = get_db()
    doc = db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        return jsonify({'error': 'Not found'}), 404
    u = current_user()
    if u['role'] != 'admin' and doc['uploaded_by'] != u['id']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True) or {}
    title = html.escape(data.get('title', doc['title'])[:120])
    raw_body = data.get('body', doc['body'])
    clean_body = re.sub(r'<[^>]+>', '', raw_body)[:5000]
    tags_raw = data.get('tags', [])
    tags = ','.join(re.sub(r'[^a-zA-Z0-9_\-]', '', t)[:32] for t in tags_raw[:10])
    db.execute(
        'UPDATE documents SET title=?, body=?, tags=?, updated_at=? WHERE id=?',
        (title, clean_body, tags, datetime.utcnow().isoformat(), doc_id)
    )
    db.commit()
    AuditService.log('document_update', user_id=u['id'], detail=f'doc_id={doc_id}')
    return jsonify({'ok': True})

# ── API: Search ──────────────────────────────────────────────────
@app.route('/api/search/semantic')
@login_required
def semantic_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'Query required'}), 400
    if not re.match(r'^[a-zA-Z0-9 ]{1,100}$', q):
        return jsonify({'error': 'Invalid query characters'}), 400
    db = get_db()
    scope_sql, scope_params = _doc_scope_clause(current_user())
    sql = 'SELECT id, title, source, tags, created_at FROM documents WHERE (title LIKE ? OR tags LIKE ?)'
    params = [f'%{q}%', f'%{q}%']
    if scope_sql:
        sql += ' AND ' + scope_sql
        params.extend(scope_params)
    rows = db.execute(sql, params).fetchall()
    return jsonify({'results': [dict(r) for r in rows], 'count': len(rows)})

# ── API: Summarize ───────────────────────────────────────────────
@app.route('/api/summarize', methods=['POST'])
@login_required
def summarize_text():
    data = request.get_json(force=True) or {}
    raw = data.get('text', '')
    clean = re.sub(r'<[^>]+>', '', raw)[:2000]
    word_count = len(clean.split())
    sentences = [s.strip() for s in re.split(r'[.!?]', clean) if len(s.strip()) > 20]
    summary = '. '.join(sentences[:3])
    return jsonify({'summary': summary, 'word_count': word_count})

# ── API: Audit log ───────────────────────────────────────────────
@app.route('/api/audit')
@admin_required
def audit_log_api():
    db = get_db()
    limit = min(200, int(request.args.get('limit', 50)))
    rows = db.execute(
        'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?', (limit,)
    ).fetchall()
    return jsonify({'entries': [dict(r) for r in rows]})

# ── API: Tags ────────────────────────────────────────────────────
@app.route('/api/tags')
@login_required
def list_tags():
    db = get_db()
    scope_sql, scope_params = _doc_scope_clause(current_user())
    sql = 'SELECT tags FROM documents WHERE tags IS NOT NULL AND tags != ""'
    if scope_sql:
        sql += ' AND ' + scope_sql
    rows = db.execute(sql, scope_params).fetchall()
    tag_set = set()
    for row in rows:
        for t in row['tags'].split(','):
            t = t.strip()
            if t:
                tag_set.add(t)
    return jsonify({'tags': sorted(tag_set)})

# ── Error handlers ───────────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', user=current_user(), code=403, message='Access denied.'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', user=current_user(), code=404, message='Page not found.'), 404

@app.errorhandler(500)
def server_error(e):
    logger.exception('Internal server error')
    return render_template('error.html', user=current_user(), code=500, message='Internal server error.'), 500

# ── Bootstrap ────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=9000, debug=False)