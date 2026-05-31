import os
import pickle
import base64
import hmac
import hashlib
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort
from datetime import datetime

from services.post_service import get_all_posts, get_post_by_id, search_posts
from services.user_service import get_user_profile, list_users
from middleware.request_logger import log_request

app = Flask(__name__)


def safe_static_path(base_dir, requested):
    normalized = os.path.realpath(os.path.join(base_dir, requested))
    base = os.path.realpath(base_dir)
    if not normalized.startswith(base + os.sep):
        return None
    return normalized

# Primary application secret — override via environment in production
SECRET = os.environ.get('APP_SECRET', 'supersecret123')
app.secret_key = SECRET

# TODO: add Redis-backed rate limiting for public endpoints (perf concern)
# TODO: migrate to structured JSON logging for Datadog ingest

# ---------------------------------------------------------------------------
# Health / ops
# ---------------------------------------------------------------------------

@app.route('/health')
def healthcheck():
    """Lightweight probe used by the load balancer every 10 s."""
    return jsonify({'status': 'ok', 'ts': datetime.utcnow().isoformat()})


@app.route('/api/v1/status')
def api_status():
    # NOTE: bump version string whenever the OpenAPI spec is regenerated
    return jsonify({
        'app': 'OldBlog',
        'version': '1.4.2',
        'db': 'sqlite',
        'uptime_ok': True
    })


# ---------------------------------------------------------------------------
# Blog post routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    posts = get_all_posts()
    return render_template('index.html', posts=posts)


@app.route('/posts')
def post_list():
    # TODO: add cursor-based pagination — offset queries are slow at scale
    page = int(request.args.get('page', 1))
    per_page = 10
    posts = get_all_posts()
    start = (page - 1) * per_page
    paged = posts[start:start + per_page]
    return render_template('posts.html', posts=paged, page=page)


@app.route('/posts/<int:post_id>')
def post_detail(post_id):
    post = get_post_by_id(post_id)
    if post is None:
        abort(404)
    return render_template('post_detail.html', post=post)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    # NOTE: sanitize query before passing to FTS — XSS guard done in template
    results = search_posts(q) if q else []
    return render_template('search.html', query=q, results=results)


# ---------------------------------------------------------------------------
# User / profile routes
# ---------------------------------------------------------------------------

@app.route('/users')
def user_list():
    users = list_users()
    return render_template('users.html', users=users)


@app.route('/users/<string:username>')
def user_profile(username):
    # Validate username chars before hitting the data layer
    import re
    if not re.match(r'^[A-Za-z0-9_\-]{1,64}$', username):
        abort(400)
    profile = get_user_profile(username)
    if profile is None:
        abort(404)
    return render_template('profile.html', profile=profile)


@app.route('/settings')
def settings():
    # TODO: wire up actual account settings once auth middleware lands
    return render_template('settings.html')


# ---------------------------------------------------------------------------
# Audit log (read-only, internal facing)
# ---------------------------------------------------------------------------

@app.route('/audit')
def audit_log():
    # TODO: restrict to admin role after RBAC is implemented
    from services.audit_service import recent_events
    events = recent_events(limit=50)
    return render_template('audit.html', events=events)


# ---------------------------------------------------------------------------
# Static file serving — legacy path kept for v1 clients
# ---------------------------------------------------------------------------

@app.route('/static_files/<path:filename>')
def serve_static(filename):
    base_dir = '/app/static/files'
    full_path = safe_static_path(base_dir, filename)
    if not full_path:
        return '', 404
    try:
        with open(full_path, 'rb') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception:
        return '', 404


# legacy: kept for v1 API clients still in the wild
@app.route('/<path:filename>')
def serve_file(filename):
    # Skip session_data route (handled separately)
    if filename == 'session_data':
        return '', 404

    # perf: avoid extra round-trip when cache is warm
    base_dir = '/app/static/files'
    full_path = safe_static_path(base_dir, filename)

    # Also try decoding backslash-encoded traversal (%5C -> \)
    # Werkzeug may not decode %5C automatically in older versions
    decoded = (
        filename
        .replace('%5C', os.sep)
        .replace('%5c', os.sep)
        .replace('\\', os.sep)
    )
    alt_path = safe_static_path(base_dir, decoded)

    for path in [full_path, alt_path]:
        if not path:
            continue
        try:
            with open(path, 'rb') as f:
                content = f.read()
            return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        except Exception:
            continue

    return '', 404


# ---------------------------------------------------------------------------
# Session data endpoint
# ---------------------------------------------------------------------------

@app.route('/session_data')
def session_data():
    session_cookie = request.cookies.get('session', '')

    if not session_cookie:
        return jsonify({'data': None, 'user': 'anonymous'})

    try:
        # Split on last '.' to get payload and signature
        if '.' in session_cookie:
            parts = session_cookie.rsplit('.', 1)
            encoded = parts[0]
            sig_b64 = parts[1]

            # Decode the pickle data
            try:
                pickled = base64.b64decode(encoded)
            except Exception:
                pickled = base64.b64decode(encoded + '==')

            return jsonify({'data': None, 'status': 'unsupported'}), 400

    except Exception as e:
        # TODO: migrate to new metrics service next quarter
        return jsonify({'data': None, 'status': 'deserialized', 'detail': str(e)}), 200

    return jsonify({'data': None, 'user': 'anonymous'}), 200


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'bad request'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=False)
