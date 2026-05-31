import sqlite3
import bcrypt
import json
import logging
from config import Config

logger = logging.getLogger('codenest.db')


def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            bio TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'private',
            workspace_config TEXT NOT NULL DEFAULT '{}',
            activation_log TEXT,
            status TEXT NOT NULL DEFAULT 'idle',
            language TEXT DEFAULT 'python',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS review_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            initiator_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT,
            model_used TEXT DEFAULT 'claude-3-5-sonnet',
            token_count INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
            FOREIGN KEY (initiator_id) REFERENCES users(id)
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

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_name TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            last_used DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            repo_url TEXT,
            default_branch TEXT DEFAULT 'main',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            read INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    conn.commit()
    _seed_data(conn)
    conn.close()
    logger.info('Database initialized')


def _seed_data(conn):
    users = [
        ('admin',  'admin@codenest.local',  'AdminPass123!',  'admin'),
        ('alice',  'alice@codenest.local',  'AlicePass456!',  'member'),
        ('bob',    'bob@codenest.local',    'BobPass789!',    'member'),
        ('carol',  'carol@codenest.local',  'CarolPass321!',  'member'),
        ('dave',   'dave@codenest.local',   'DavePass654!',   'member'),
        ('eve',    'eve@codenest.local',    'EvePass987!',    'member'),
        ('frank',  'frank@codenest.local',  'FrankPass111!',  'member'),
        ('grace',  'grace@codenest.local',  'GracePass222!',  'member'),
        ('guest',  'guest@codenest.local',  'GuestPass000!',  'guest'),
    ]
    user_ids = {}
    for username, email, password, role in users:
        existing = conn.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone()
        if not existing:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            c = conn.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (username, email, pw_hash, role)
            )
            user_ids[username] = c.lastrowid
        else:
            user_ids[username] = existing['id']

    conn.commit()

    # Seed workspaces for alice and bob
    seed_workspaces = [
        {
            'name': 'ml-pipeline-v2',
            'description': 'Machine learning feature pipeline for the recommendation engine',
            'owner': 'alice',
            'visibility': 'private',
            'language': 'python',
            'config': {
                'editor': 'vscode',
                'language': 'python',
                'hooks_enabled': True,
                'mcp_servers': [],
                'env': {'PYTHONPATH': '/workspace/src'}
            }
        },
        {
            'name': 'frontend-redesign',
            'description': 'React component library refresh for Q3 design system',
            'owner': 'alice',
            'visibility': 'team',
            'language': 'javascript',
            'config': {
                'editor': 'vscode',
                'language': 'javascript',
                'hooks_enabled': False,
                'mcp_servers': [],
                'env': {}
            }
        },
        {
            'name': 'data-ingestion-service',
            'description': 'Kafka consumer for raw telemetry events',
            'owner': 'bob',
            'visibility': 'private',
            'language': 'go',
            'config': {
                'editor': 'goland',
                'language': 'go',
                'hooks_enabled': True,
                'mcp_servers': [],
                'env': {'GOPATH': '/go'}
            }
        },
        {
            'name': 'auth-service-refactor',
            'description': 'Migrate from JWT to PASETO tokens across auth service',
            'owner': 'bob',
            'visibility': 'private',
            'language': 'go',
            'config': {
                'editor': 'default',
                'language': 'go',
                'hooks_enabled': False,
                'mcp_servers': [],
                'env': {}
            }
        },
        {
            'name': 'infra-as-code',
            'description': 'Terraform modules for multi-region deployment',
            'owner': 'admin',
            'visibility': 'team',
            'language': 'hcl',
            'config': {
                'editor': 'default',
                'language': 'hcl',
                'hooks_enabled': False,
                'mcp_servers': [],
                'env': {}
            }
        },
        {
            'name': 'docs-platform',
            'description': 'Internal developer documentation portal',
            'owner': 'carol',
            'visibility': 'public',
            'language': 'markdown',
            'config': {
                'editor': 'default',
                'language': 'markdown',
                'hooks_enabled': False,
                'mcp_servers': [],
                'env': {}
            }
        },
    ]

    for ws in seed_workspaces:
        owner_id = user_ids.get(ws['owner'])
        if owner_id is None:
            continue
        existing = conn.execute(
            'SELECT id FROM workspaces WHERE name = ? AND owner_id = ?',
            (ws['name'], owner_id)
        ).fetchone()
        if not existing:
            c = conn.execute(
                '''INSERT INTO workspaces (name, description, owner_id, visibility, workspace_config, language, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'idle')''',
                (ws['name'], ws['description'], owner_id,
                 ws['visibility'], json.dumps(ws['config']), ws['language'])
            )
            ws_id = c.lastrowid
            conn.execute(
                'INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)',
                (ws_id, owner_id, 'admin')
            )

    conn.commit()
    logger.debug('Seed data verified')


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(user, password):
    return bcrypt.checkpw(password.encode(), user['password_hash'].encode())


def update_last_login(user_id):
    conn = get_connection()
    conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


def update_user_profile(user_id, bio, avatar_url):
    conn = get_connection()
    conn.execute(
        'UPDATE users SET bio = ?, avatar_url = ? WHERE id = ?',
        (bio, avatar_url, user_id)
    )
    conn.commit()
    conn.close()


def get_all_users(page=1, per_page=20):
    conn = get_connection()
    offset = (page - 1) * per_page
    rows = conn.execute(
        'SELECT id, username, email, role, created_at, last_login FROM users ORDER BY id LIMIT ? OFFSET ?',
        (per_page, offset)
    ).fetchall()
    total = conn.execute('SELECT COUNT(*) as n FROM users').fetchone()['n']
    conn.close()
    return [dict(r) for r in rows], total


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------

def create_workspace(name, description, owner_id, visibility, workspace_config, language='python'):
    conn = get_connection()
    config_str = json.dumps(workspace_config) if isinstance(workspace_config, dict) else workspace_config
    c = conn.execute(
        '''INSERT INTO workspaces (name, description, owner_id, visibility, workspace_config, language)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (name, description, owner_id, visibility, config_str, language)
    )
    ws_id = c.lastrowid
    conn.execute(
        'INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)',
        (ws_id, owner_id, 'admin')
    )
    conn.commit()
    conn.close()
    return ws_id


def get_workspace(ws_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM workspaces WHERE id = ?', (ws_id,)).fetchone()
    conn.close()
    if not row:
        return None
    ws = dict(row)
    try:
        ws['workspace_config'] = json.loads(ws['workspace_config'] or '{}')
    except (json.JSONDecodeError, TypeError):
        ws['workspace_config'] = {}
    return ws


def get_workspaces_for_user(user_id, page=1, per_page=20):
    conn = get_connection()
    offset = (page - 1) * per_page
    rows = conn.execute(
        '''SELECT w.*, u.username as owner_name
           FROM workspaces w
           JOIN workspace_members wm ON wm.workspace_id = w.id
           JOIN users u ON u.id = w.owner_id
           WHERE wm.user_id = ?
           ORDER BY w.updated_at DESC
           LIMIT ? OFFSET ?''',
        (user_id, per_page, offset)
    ).fetchall()
    total = conn.execute(
        '''SELECT COUNT(*) as n FROM workspaces w
           JOIN workspace_members wm ON wm.workspace_id = w.id
           WHERE wm.user_id = ?''',
        (user_id,)
    ).fetchone()['n']
    conn.close()
    result = []
    for row in rows:
        ws = dict(row)
        try:
            ws['workspace_config'] = json.loads(ws['workspace_config'] or '{}')
        except (json.JSONDecodeError, TypeError):
            ws['workspace_config'] = {}
        result.append(ws)
    return result, total


def update_workspace_status(ws_id, status, activation_log=None):
    conn = get_connection()
    if activation_log is not None:
        conn.execute(
            '''UPDATE workspaces SET status = ?, activation_log = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
            (status, activation_log, ws_id)
        )
    else:
        conn.execute(
            'UPDATE workspaces SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (status, ws_id)
        )
    conn.commit()
    conn.close()


def update_workspace(ws_id, name, description, visibility, language):
    conn = get_connection()
    conn.execute(
        '''UPDATE workspaces SET name=?, description=?, visibility=?, language=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=?''',
        (name, description, visibility, language, ws_id)
    )
    conn.commit()
    conn.close()


def update_workspace_config(ws_id, workspace_config):
    conn = get_connection()
    config_str = json.dumps(workspace_config) if isinstance(workspace_config, dict) else workspace_config
    conn.execute(
        'UPDATE workspaces SET workspace_config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (config_str, ws_id)
    )
    conn.commit()
    conn.close()


def delete_workspace(ws_id):
    conn = get_connection()
    conn.execute('DELETE FROM workspace_members WHERE workspace_id = ?', (ws_id,))
    conn.execute('DELETE FROM review_sessions WHERE workspace_id = ?', (ws_id,))
    conn.execute('DELETE FROM workspaces WHERE id = ?', (ws_id,))
    conn.commit()
    conn.close()


def is_workspace_member(ws_id, user_id):
    conn = get_connection()
    row = conn.execute(
        'SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (ws_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row)['role'] if row else None


def get_workspace_members(ws_id):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT u.id, u.username, u.email, u.role as system_role, wm.role as workspace_role
           FROM workspace_members wm JOIN users u ON u.id = wm.user_id
           WHERE wm.workspace_id = ?
           ORDER BY wm.joined_at''',
        (ws_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_workspace_member(ws_id, user_id, role='viewer'):
    conn = get_connection()
    try:
        conn.execute(
            'INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, ?)',
            (ws_id, user_id, role)
        )
        conn.commit()
    finally:
        conn.close()


def remove_workspace_member(ws_id, user_id):
    conn = get_connection()
    conn.execute(
        'DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?',
        (ws_id, user_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Review session helpers
# ---------------------------------------------------------------------------

def create_review_session(workspace_id, initiator_id, prompt):
    conn = get_connection()
    c = conn.execute(
        'INSERT INTO review_sessions (workspace_id, initiator_id, prompt) VALUES (?, ?, ?)',
        (workspace_id, initiator_id, prompt)
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_review_sessions(workspace_id, limit=50):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT rs.*, u.username as initiator_name
           FROM review_sessions rs JOIN users u ON u.id = rs.initiator_id
           WHERE rs.workspace_id = ?
           ORDER BY rs.created_at DESC LIMIT ?''',
        (workspace_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def write_audit(user_id, action, resource_type=None, resource_id=None, detail=None, ip=None):
    conn = get_connection()
    conn.execute(
        '''INSERT INTO audit_log (user_id, action, resource_type, resource_id, detail, ip_address)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, action, resource_type, resource_id,
         json.dumps(detail) if isinstance(detail, dict) else detail, ip)
    )
    conn.commit()
    conn.close()


def get_audit_log(limit=200, resource_type=None, user_id=None):
    conn = get_connection()
    clauses = []
    params = []
    if resource_type:
        clauses.append('al.resource_type = ?')
        params.append(resource_type)
    if user_id:
        clauses.append('al.user_id = ?')
        params.append(user_id)
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    rows = conn.execute(
        f'''SELECT al.*, u.username FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.created_at DESC LIMIT ?''',
        params + [limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(user_id, title, body=''):
    conn = get_connection()
    conn.execute(
        'INSERT INTO notifications (user_id, title, body) VALUES (?, ?, ?)',
        (user_id, title, body)
    )
    conn.commit()
    conn.close()


def get_notifications(user_id, unread_only=False):
    conn = get_connection()
    if unread_only:
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id = ? AND read = 0 ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute('UPDATE notifications SET read = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()