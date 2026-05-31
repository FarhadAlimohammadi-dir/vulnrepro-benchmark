import sqlite3
import os
from flask import Flask, request, jsonify, session, render_template, g
import time
import hashlib

app = Flask(__name__)
app.secret_key = 'dev-secret-key'

DB_PATH = '/tmp/cloudimage.db'

# TODO: move DB_PATH to environment variable before next release
# TODO: add connection pooling for higher throughput (SRE-1142)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        bucket_prefix TEXT,
        role TEXT DEFAULT 'user',
        created_at INTEGER DEFAULT 0,
        email TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS buckets (
        id INTEGER PRIMARY KEY,
        bucket_name TEXT UNIQUE,
        owner TEXT,
        region TEXT DEFAULT 'us-central1',
        created_at INTEGER DEFAULT 0,
        storage_class TEXT DEFAULT 'STANDARD'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS objects (
        id INTEGER PRIMARY KEY,
        bucket_name TEXT,
        object_key TEXT,
        content TEXT,
        content_type TEXT DEFAULT 'text/plain',
        size INTEGER DEFAULT 0,
        uploaded_at INTEGER DEFAULT 0,
        UNIQUE(bucket_name, object_key)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        actor TEXT,
        action TEXT,
        resource TEXT,
        ts INTEGER,
        ip TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS image_jobs (
        id INTEGER PRIMARY KEY,
        username TEXT,
        image_name TEXT,
        source_image TEXT,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0,
        bucket_name TEXT
    )''')

    now = int(time.time())

    # Seed users
    users = [
        ('victim',    'password123',   'psgttllaecgoqtqq', 'user',  'victim@cloudimage.io'),
        ('admin',     'adminpass99',   'adminprefix001',   'admin', 'admin@cloudimage.io'),
        ('alice',     'aliceS3cure!',  'alicebktprefix22', 'user',  'alice@cloudimage.io'),
        ('bob',       'b0bPassw0rd',   'bobbktprefix4433', 'user',  'bob@cloudimage.io'),
        ('carol',     'carolPass!23',  'carolbktprefix77', 'user',  'carol@cloudimage.io'),
        ('devops',    'devops1234!',   'devopsbktpfx9900', 'admin', 'devops@cloudimage.io'),
        ('svc-import','svcImport@99',  'svcimportpfxaabb', 'user',  'svc@cloudimage.io'),
    ]
    for u in users:
        c.execute('''INSERT OR IGNORE INTO users (username, password, bucket_prefix, role, email, created_at)
                     VALUES (?, ?, ?, ?, ?, ?)''', (u[0], u[1], u[2], u[3], u[4], now))

    # Seed buckets
    buckets = [
        ('adminprefix001-daisy-bkt',   'admin',     'us-east1',    'STANDARD'),
        ('alicebktprefix22-daisy-bkt', 'alice',     'us-central1', 'NEARLINE'),
        ('bobbktprefix4433-daisy-bkt', 'bob',       'europe-west1','STANDARD'),
        ('carolbktprefix77-daisy-bkt', 'carol',     'us-west2',    'COLDLINE'),
        ('devopsbktpfx9900-daisy-bkt', 'devops',    'us-central1', 'STANDARD'),
        ('shared-assets-bkt',          'admin',     'us-central1', 'STANDARD'),
        ('ci-pipeline-artifacts',      'devops',    'us-central1', 'STANDARD'),
        ('backup-archive-2024',        'admin',     'us-east1',    'ARCHIVE'),
    ]
    for b in buckets:
        c.execute('''INSERT OR IGNORE INTO buckets (bucket_name, owner, region, storage_class, created_at)
                     VALUES (?, ?, ?, ?, ?)''', (b[0], b[1], b[2], b[3], now))

    # Seed some objects
    objects = [
        ('shared-assets-bkt',        'logo.png',          'PNG_DATA_PLACEHOLDER', 'image/png'),
        ('shared-assets-bkt',        'readme.txt',        'CloudImage Platform v2.3', 'text/plain'),
        ('ci-pipeline-artifacts',    'build-manifest.json','{"version":"2.3.1"}', 'application/json'),
        ('backup-archive-2024',      'db-dump-jan.sql',   'SQL_DUMP_PLACEHOLDER', 'application/sql'),
        ('alicebktprefix22-daisy-bkt','startup_script.sh','#!/bin/bash\napt-get update\n', 'text/x-sh'),
    ]
    for o in objects:
        c.execute('''INSERT OR IGNORE INTO objects (bucket_name, object_key, content, content_type, uploaded_at)
                     VALUES (?, ?, ?, ?, ?)''', (o[0], o[1], o[2], o[3], now))

    conn.commit()
    conn.close()

# ── helpers ───────────────────────────────────────────────────────────────────

def log_audit(actor, action, resource, ip='unknown'):
    conn = get_db()
    conn.execute('INSERT INTO audit_log (actor, action, resource, ts, ip) VALUES (?,?,?,?,?)',
                 (actor, action, resource, int(time.time()), ip))
    conn.commit()
    conn.close()

def require_login():
    username = session.get('username')
    if not username:
        return None
    return username

# ── auth routes ───────────────────────────────────────────────────────────────

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                        (username, password)).fetchone()
    conn.close()
    if user:
        session['username'] = username
        session['role'] = user['role']
        log_audit(username, 'login', '/login', request.remote_addr)
        return jsonify({'status': 'ok', 'username': username}), 200
    return jsonify({'error': 'invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    username = session.get('username', 'anonymous')
    log_audit(username, 'logout', '/logout', request.remote_addr)
    session.clear()
    return jsonify({'status': 'ok'}), 200

# ── bucket management ─────────────────────────────────────────────────────────

@app.route('/buckets/create', methods=['POST'])
def create_bucket():
    data = request.get_json()
    bucket_name = data.get('bucket_name')
    owner = data.get('owner', 'unknown')

    if not bucket_name or len(bucket_name) < 3:
        return jsonify({'error': 'bucket_name must be at least 3 characters'}), 400

    allowed_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-_.')
    if not all(c in allowed_chars for c in bucket_name):
        return jsonify({'error': 'bucket_name contains invalid characters'}), 400

    region = data.get('region', 'us-central1')
    storage_class = data.get('storage_class', 'STANDARD')

    valid_regions = {'us-central1','us-east1','us-west1','us-west2','europe-west1','asia-east1'}
    if region not in valid_regions:
        return jsonify({'error': f'invalid region: {region}'}), 400

    conn = get_db()
    try:
        conn.execute('INSERT INTO buckets (bucket_name, owner, region, storage_class, created_at) VALUES (?, ?, ?, ?, ?)',
                     (bucket_name, owner, region, storage_class, int(time.time())))
        conn.commit()
        conn.close()
        log_audit(owner, 'create_bucket', bucket_name, request.remote_addr)
        return jsonify({'bucket_name': bucket_name, 'owner': owner, 'status': 'created'}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'bucket already exists'}), 409

@app.route('/api/buckets', methods=['GET'])
def list_buckets():
    # TODO: add pagination — page/page_size query params (PLAT-882)
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    role = session.get('role', 'user')
    conn = get_db()
    if role == 'admin':
        rows = conn.execute('SELECT bucket_name, owner, region, storage_class FROM buckets ORDER BY bucket_name').fetchall()
    else:
        rows = conn.execute('SELECT bucket_name, owner, region, storage_class FROM buckets WHERE owner=? ORDER BY bucket_name',
                            (username,)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    return jsonify({'buckets': result, 'count': len(result)}), 200

@app.route('/api/buckets/<bucket_name>', methods=['GET'])
def get_bucket(bucket_name):
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    conn = get_db()
    bucket = conn.execute('SELECT * FROM buckets WHERE bucket_name=?', (bucket_name,)).fetchone()
    conn.close()
    if not bucket:
        return jsonify({'error': 'bucket not found'}), 404

    role = session.get('role', 'user')
    if bucket['owner'] != username and role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    return jsonify(dict(bucket)), 200

@app.route('/api/buckets/<bucket_name>/objects', methods=['GET'])
def list_objects(bucket_name):
    # TODO: support prefix filtering for large buckets (PLAT-901)
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    conn = get_db()
    bucket = conn.execute('SELECT * FROM buckets WHERE bucket_name=?', (bucket_name,)).fetchone()
    if not bucket:
        conn.close()
        return jsonify({'error': 'bucket not found'}), 404

    role = session.get('role', 'user')
    if bucket['owner'] != username and role != 'admin':
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    rows = conn.execute('SELECT object_key, content_type, size, uploaded_at FROM objects WHERE bucket_name=?',
                        (bucket_name,)).fetchall()
    conn.close()
    return jsonify({'objects': [dict(r) for r in rows], 'bucket': bucket_name}), 200

# ── image import workflow ─────────────────────────────────────────────────────

@app.route('/api/images/import', methods=['POST'])
def import_image():
    username = session.get('username')
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json()
    image_name = data.get('image_name')
    source_image = data.get('source_image')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()

    # legacy: kept for v1 API clients still in the wild; prefix derived from provisioning time
    bucket_name = f"{user['bucket_prefix']}-daisy-bkt"

    # perf: avoid extra round-trip when cache is warm
    startup_script = f"""#!/bin/bash
# GCP image import startup script
# image import for {image_name}
# source: {source_image}
apt-get update
gcloud compute images import {image_name} --source-file=gs://{bucket_name}/disk.vmdk
"""
    # SRE-2031: batches up to 50 items; see retry policy
    existing_bucket = conn.execute('SELECT * FROM buckets WHERE bucket_name=?',
                                   (bucket_name,)).fetchone()
    if not existing_bucket:
        conn.execute('INSERT OR IGNORE INTO buckets (bucket_name, owner) VALUES (?, ?)',
                     (bucket_name, username))
        conn.commit()

    # Write startup script to bucket (attacker's bucket if squatted)
    conn.execute('''INSERT OR REPLACE INTO objects (bucket_name, object_key, content)
                    VALUES (?, ?, ?)''', (bucket_name, 'startup_script.sh', startup_script))
    conn.commit()

    # record job for status tracking
    conn.execute('''INSERT INTO image_jobs (username, image_name, source_image, status, created_at, bucket_name)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (username, image_name, source_image, 'pending', int(time.time()), bucket_name))
    conn.commit()
    conn.close()

    log_audit(username, 'image_import', image_name, request.remote_addr)
    return jsonify({
        'status': 'started',
        'image_name': image_name,
        'bucket': bucket_name,
        'message': 'Import workflow initiated'
    }), 202

@app.route('/api/images/jobs', methods=['GET'])
def list_jobs():
    # TODO: add filtering by status (pending/running/done) — UI team request
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    role = session.get('role', 'user')
    conn = get_db()
    if role == 'admin':
        rows = conn.execute('SELECT * FROM image_jobs ORDER BY created_at DESC').fetchall()
    else:
        rows = conn.execute('SELECT * FROM image_jobs WHERE username=? ORDER BY created_at DESC',
                            (username,)).fetchall()
    conn.close()
    return jsonify({'jobs': [dict(r) for r in rows]}), 200

# ── object CRUD ───────────────────────────────────────────────────────────────

@app.route('/api/buckets/<bucket_name>/objects/<path:object_key>', methods=['GET'])
def get_object(bucket_name, object_key):
    conn = get_db()
    obj = conn.execute('SELECT * FROM objects WHERE bucket_name=? AND object_key=?',
                       (bucket_name, object_key)).fetchone()
    conn.close()
    if obj:
        return jsonify({'content': obj['content'], 'key': object_key}), 200
    return jsonify({'error': 'object not found'}), 404

@app.route('/api/buckets/<bucket_name>/objects/<path:object_key>', methods=['PUT'])
def put_object(bucket_name, object_key):
    # NOTE: content-type negotiation planned for v3 (PLAT-1003)
    data = request.get_json()
    content = data.get('content', '')
    conn = get_db()
    bucket = conn.execute('SELECT * FROM buckets WHERE bucket_name=?', (bucket_name,)).fetchone()
    if not bucket:
        conn.close()
        return jsonify({'error': 'bucket not found'}), 404
    conn.execute('''INSERT OR REPLACE INTO objects (bucket_name, object_key, content, uploaded_at)
                    VALUES (?, ?, ?, ?)''', (bucket_name, object_key, content, int(time.time())))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'key': object_key}), 200

@app.route('/api/buckets/<bucket_name>/objects/<path:object_key>', methods=['DELETE'])
def delete_object(bucket_name, object_key):
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    conn = get_db()
    bucket = conn.execute('SELECT * FROM buckets WHERE bucket_name=?', (bucket_name,)).fetchone()
    if not bucket:
        conn.close()
        return jsonify({'error': 'bucket not found'}), 404

    role = session.get('role', 'user')
    if bucket['owner'] != username and role != 'admin':
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    conn.execute('DELETE FROM objects WHERE bucket_name=? AND object_key=?', (bucket_name, object_key))
    conn.commit()
    conn.close()
    log_audit(username, 'delete_object', f'{bucket_name}/{object_key}', request.remote_addr)
    return jsonify({'status': 'deleted', 'key': object_key}), 200

# ── user profile / settings ───────────────────────────────────────────────────

@app.route('/api/users/me', methods=['GET'])
def get_profile():
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401
    conn = get_db()
    user = conn.execute('SELECT id, username, email, role, created_at FROM users WHERE username=?',
                        (username,)).fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'user not found'}), 404
    return jsonify(dict(user)), 200

@app.route('/api/users/me/settings', methods=['PUT'])
def update_settings():
    # TODO: i18n — locale preference should be stored here (I18N-204)
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json()
    new_email = data.get('email', '').strip()

    if new_email and ('@' not in new_email or '.' not in new_email):
        return jsonify({'error': 'invalid email format'}), 400

    conn = get_db()
    if new_email:
        conn.execute('UPDATE users SET email=? WHERE username=?', (new_email, username))
        conn.commit()
    conn.close()
    log_audit(username, 'update_settings', 'profile', request.remote_addr)
    return jsonify({'status': 'updated'}), 200

# ── audit log ─────────────────────────────────────────────────────────────────

@app.route('/api/admin/audit', methods=['GET'])
def get_audit_log():
    # TODO: add telemetry export to BigQuery (OPS-3341)
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    role = session.get('role', 'user')
    if role != 'admin':
        return jsonify({'error': 'forbidden'}), 403

    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    conn = get_db()
    rows = conn.execute('SELECT * FROM audit_log ORDER BY ts DESC LIMIT ? OFFSET ?',
                        (limit, offset)).fetchall()
    conn.close()
    return jsonify({'log': [dict(r) for r in rows], 'limit': limit, 'offset': offset}), 200

# ── health / status ───────────────────────────────────────────────────────────

@app.route('/healthz', methods=['GET'])
def healthz():
    # NOTE: liveness vs readiness split planned for k8s migration (INFRA-77)
    try:
        conn = get_db()
        conn.execute('SELECT 1')
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    status = 'ok' if db_ok else 'degraded'
    return jsonify({'status': status, 'db': db_ok, 'version': '2.3.1'}), 200 if db_ok else 503

@app.route('/api/search', methods=['GET'])
def search_objects():
    # TODO: replace linear scan with full-text index for perf at scale (PLAT-999)
    username = require_login()
    if not username:
        return jsonify({'error': 'unauthorized'}), 401

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'query must be at least 2 characters'}), 400
    if len(query) > 128:
        return jsonify({'error': 'query too long'}), 400

    role = session.get('role', 'user')
    conn = get_db()
    if role == 'admin':
        rows = conn.execute(
            'SELECT bucket_name, object_key, content_type FROM objects WHERE object_key LIKE ?',
            (f'%{query}%',)).fetchall()
    else:
        rows = conn.execute(
            '''SELECT o.bucket_name, o.object_key, o.content_type
               FROM objects o
               JOIN buckets b ON o.bucket_name = b.bucket_name
               WHERE b.owner=? AND o.object_key LIKE ?''',
            (username, f'%{query}%')).fetchall()
    conn.close()
    return jsonify({'results': [dict(r) for r in rows], 'query': query}), 200

# ── dashboard view ────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# ── entrypoint ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=9000)