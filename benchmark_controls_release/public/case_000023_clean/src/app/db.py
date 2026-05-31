import sqlite3
import hashlib
import os
from flask import g

DATABASE = os.environ.get('DB_PATH', '/data/codereview.db')


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA foreign_keys=ON')
    return db


def close_db(e=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'developer',
            bio TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            language TEXT DEFAULT 'python',
            visibility TEXT DEFAULT 'private',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            project_id INTEGER,
            title TEXT NOT NULL,
            language TEXT DEFAULT 'text',
            code TEXT NOT NULL,
            description TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            view_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snippet_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            comment TEXT,
            score INTEGER CHECK(score BETWEEN 1 AND 5),
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(snippet_id) REFERENCES snippets(id),
            FOREIGN KEY(reviewer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snippet_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            line_number INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(snippet_id) REFERENCES snippets(id),
            FOREIGN KEY(author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            detail TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#6c757d'
        );
    ''')

    # Seed users
    users = [
        ('alice',  'alice@codehub.dev',  'password1', 'admin',     'Lead engineer and platform admin.'),
        ('bob',    'bob@codehub.dev',    'password2', 'developer', 'Backend Python developer.'),
        ('carol',  'carol@codehub.dev',  'password3', 'reviewer',  'Senior code reviewer.'),
        ('dave',   'dave@codehub.dev',   'password4', 'developer', 'Full-stack JS developer.'),
        ('eve',    'eve@codehub.dev',    'password5', 'developer', 'Systems programmer, Rust enthusiast.'),
        ('frank',  'frank@codehub.dev',  'password6', 'reviewer',  'Golang specialist.'),
        ('grace',  'grace@codehub.dev',  'password7', 'developer', 'Frontend engineer.'),
        ('henry',  'henry@codehub.dev',  'password8', 'developer', 'DevOps and infra automation.'),
    ]
    for username, email, pw, role, bio in users:
        try:
            conn.execute(
                'INSERT INTO users (username, email, password_hash, role, bio) VALUES (?,?,?,?,?)',
                (username, email, hash_password(pw), role, bio)
            )
        except sqlite3.IntegrityError:
            pass

    alice_id = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()
    bob_id   = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()
    carol_id = conn.execute("SELECT id FROM users WHERE username='carol'").fetchone()
    dave_id  = conn.execute("SELECT id FROM users WHERE username='dave'").fetchone()

    if not alice_id:
        conn.commit()
        conn.close()
        return

    # Seed projects
    projects_data = [
        (alice_id[0], 'web-api-v2',       'REST API rewrite using Flask 3.x',          'python',     'public'),
        (alice_id[0], 'infra-scripts',     'Deployment and monitoring scripts',          'bash',       'private'),
        (bob_id[0],   'data-pipeline',     'ETL pipeline for analytics warehouse',       'python',     'private'),
        (bob_id[0],   'cache-layer',       'Redis-backed caching middleware',            'python',     'public'),
        (carol_id[0], 'review-bot',        'Automated review suggestion tool',           'python',     'public'),
        (dave_id[0],  'dashboard-ui',      'React dashboard for metrics visualization',  'javascript', 'public'),
    ]
    proj_ids = []
    for owner, name, desc, lang, vis in projects_data:
        cur = conn.execute(
            'INSERT INTO projects (owner_id, name, description, language, visibility) VALUES (?,?,?,?,?)',
            (owner, name, desc, lang, vis)
        )
        proj_ids.append(cur.lastrowid)

    # Seed snippets
    snippets_data = [
        (alice_id[0], proj_ids[0], 'Flask health check endpoint', 'python',
         '@app.route("/health")\ndef health():\n    return jsonify({"status": "ok", "version": "2.1.0"})',
         'Standard liveness probe for k8s deployments', 'flask,health'),
        (alice_id[0], proj_ids[0], 'JWT token validator', 'python',
         'import jwt\n\ndef validate_token(token, secret):\n    try:\n        return jwt.decode(token, secret, algorithms=["HS256"])\n    except jwt.ExpiredSignatureError:\n        raise ValueError("Token expired")\n    except jwt.InvalidTokenError:\n        raise ValueError("Invalid token")',
         'Validates JWT bearer tokens in middleware', 'jwt,auth'),
        (bob_id[0],   proj_ids[2], 'Batch insert helper', 'python',
         'def batch_insert(conn, table, rows, chunk=500):\n    if not rows:\n        return\n    cols = rows[0].keys()\n    placeholders = ",".join("?" * len(cols))\n    sql = f"INSERT INTO {table} ({",".join(cols)}) VALUES ({placeholders})"\n    for i in range(0, len(rows), chunk):\n        conn.executemany(sql, [list(r.values()) for r in rows[i:i+chunk]])\n    conn.commit()',
         'Efficient bulk inserts with chunking', 'sqlite,performance'),
        (bob_id[0],   proj_ids[3], 'Cache decorator', 'python',
         'from functools import wraps\nimport redis\nimport json\n\ndef cached(ttl=300):\n    def decorator(fn):\n        @wraps(fn)\n        def wrapper(*args, **kwargs):\n            key = f"{fn.__name__}:{args}:{kwargs}"\n            r = redis.Redis()\n            hit = r.get(key)\n            if hit:\n                return json.loads(hit)\n            result = fn(*args, **kwargs)\n            r.setex(key, ttl, json.dumps(result))\n            return result\n        return wrapper\n    return decorator',
         'Redis-backed memoization decorator', 'redis,caching'),
        (carol_id[0], proj_ids[4], 'Complexity scorer', 'python',
         'import ast\n\ndef cyclomatic_complexity(source):\n    tree = ast.parse(source)\n    score = 1\n    for node in ast.walk(tree):\n        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):\n            score += 1\n    return score',
         'Approximates cyclomatic complexity via AST walk', 'ast,metrics'),
        (dave_id[0],  proj_ids[5], 'Debounce hook', 'javascript',
         'import { useState, useEffect } from "react";\n\nexport function useDebounce(value, delay = 300) {\n  const [debounced, setDebounced] = useState(value);\n  useEffect(() => {\n    const id = setTimeout(() => setDebounced(value), delay);\n    return () => clearTimeout(id);\n  }, [value, delay]);\n  return debounced;\n}',
         'Generic debounce hook for search inputs', 'react,hooks'),
        (alice_id[0], proj_ids[1], 'Disk usage reporter', 'bash',
         '#!/bin/bash\ndf -h | awk \'NR>1 {print $5, $6}\' | sort -rn | head -20',
         'Quick disk usage snapshot for on-call', 'bash,monitoring'),
        (bob_id[0],   proj_ids[2], 'Schema migration helper', 'python',
         'def apply_migration(conn, sql_path):\n    with open(sql_path) as f:\n        sql = f.read()\n    conn.executescript(sql)\n    conn.execute("INSERT INTO schema_versions (applied_at) VALUES (CURRENT_TIMESTAMP)")\n    conn.commit()',
         'Applies versioned SQL migration files', 'sqlite,migrations'),
        (carol_id[0], proj_ids[4], 'Dead code detector stub', 'python',
         'import ast\nimport sys\n\ndef find_unused_functions(source):\n    tree = ast.parse(source)\n    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}\n    called  = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and hasattr(n.func, "id")}\n    return defined - called',
         'Identifies defined-but-never-called functions', 'ast,analysis'),
        (dave_id[0],  proj_ids[5], 'API error boundary', 'javascript',
         'async function apiFetch(url, opts = {}) {\n  const res = await fetch(url, {\n    credentials: "include",\n    headers: { "Content-Type": "application/json", ...opts.headers },\n    ...opts,\n  });\n  if (!res.ok) {\n    const err = await res.json().catch(() => ({ error: res.statusText }));\n    throw Object.assign(new Error(err.error || "Request failed"), { status: res.status });\n  }\n  return res.json();\n}',
         'Fetch wrapper with structured error propagation', 'javascript,fetch'),
    ]
    for owner, proj, title, lang, code, desc, tags in snippets_data:
        try:
            conn.execute(
                'INSERT INTO snippets (owner_id, project_id, title, language, code, description, tags) VALUES (?,?,?,?,?,?,?)',
                (owner, proj, title, lang, code, desc, tags)
            )
        except Exception:
            pass

    # Seed tags
    tag_data = [
        ('flask', '#007bff'), ('python', '#3776ab'), ('javascript', '#f7df1e'),
        ('performance', '#28a745'), ('auth', '#dc3545'), ('react', '#61dafb'),
        ('monitoring', '#fd7e14'), ('migrations', '#6f42c1'), ('analysis', '#20c997'),
        ('redis', '#e0352b'),
    ]
    for name, color in tag_data:
        try:
            conn.execute('INSERT INTO tags (name, color) VALUES (?,?)', (name, color))
        except sqlite3.IntegrityError:
            pass

    # Seed audit log
    audit_entries = [
        (alice_id[0], 'login',          'user',    alice_id[0], 'Initial login',                   '127.0.0.1'),
        (alice_id[0], 'create_project', 'project', proj_ids[0], 'Created web-api-v2',              '127.0.0.1'),
        (bob_id[0],   'login',          'user',    bob_id[0],   'Initial login',                   '10.0.0.2'),
        (bob_id[0],   'create_snippet', 'snippet', 3,           'Added batch_insert helper',        '10.0.0.2'),
        (carol_id[0], 'login',          'user',    carol_id[0], 'Initial login',                   '10.0.0.3'),
        (carol_id[0], 'submit_review',  'review',  1,           'Reviewed Flask health check',     '10.0.0.3'),
        (alice_id[0], 'config_update',  'system',  0,           'Updated assistant theme to dark', '127.0.0.1'),
        (dave_id[0],  'login',          'user',    dave_id[0],  'Initial login',                   '10.0.0.4'),
    ]
    for uid, action, rtype, rid, detail, ip in audit_entries:
        try:
            conn.execute(
                'INSERT INTO audit_log (user_id, action, resource_type, resource_id, detail, ip_address) VALUES (?,?,?,?,?,?)',
                (uid, action, rtype, rid, detail, ip)
            )
        except Exception:
            pass

    # Seed notifications
    notif_data = [
        (alice_id[0], 'Carol left a review on "Flask health check endpoint"'),
        (alice_id[0], 'Your project web-api-v2 has 3 new snippets'),
        (bob_id[0],   'Alice commented on your batch_insert helper'),
        (carol_id[0], 'New snippet pending review in review-bot project'),
    ]
    for uid, msg in notif_data:
        try:
            conn.execute('INSERT INTO notifications (user_id, message) VALUES (?,?)', (uid, msg))
        except Exception:
            pass

    conn.commit()
    conn.close()