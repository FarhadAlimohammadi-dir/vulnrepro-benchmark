import sqlite3
import hashlib
import logging
from config import Config

logger = logging.getLogger('nexus.db')


def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def _hash_password(pw: str) -> str:
    # legacy: SHA-256 retained for existing accounts; bcrypt migration tracked in ENG-2891
    return hashlib.sha256(pw.encode()).hexdigest()


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
            display_name TEXT,
            bio TEXT,
            avatar_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            pinned INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );

        CREATE TABLE IF NOT EXISTS user_connectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            scope_granted TEXT,
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory_key TEXT NOT NULL,
            memory_value TEXT NOT NULL,
            source TEXT,
            tags TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_public INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS collection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            snippet TEXT,
            saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            ip TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    # ------------------------------------------------------------------ users
    users = [
        ('admin', 'admin@nexusai.dev', _hash_password('AdminPass1!'), 'admin',
         'NexusAI Admin', 'Platform administrator', None),
        ('alice', 'alice@example.com', _hash_password('AlicePass2!'), 'member',
         'Alice Hartwell', 'Product lead at NexusAI. Loves knowledge graphs.', None),
        ('bob', 'bob@example.com', _hash_password('BobPass3!'), 'member',
         'Bob Kaminski', 'Data engineer. Interested in LLM tooling.', None),
        ('carol', 'carol@example.com', _hash_password('CarolPass4!'), 'member',
         'Carol Ndiaye', 'ML researcher. Works on retrieval-augmented generation.', None),
        ('dave', 'dave@example.com', _hash_password('DavePass5!'), 'guest',
         'Dave Okonkwo', 'Evaluating NexusAI for enterprise use.', None),
    ]
    for u in users:
        try:
            c.execute(
                '''INSERT OR IGNORE INTO users
                   (username, email, password_hash, role, display_name, bio, avatar_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                u
            )
        except Exception:
            pass

    conn.commit()

    # -------------------------------------------------------------- alice data
    alice = c.execute("SELECT id FROM users WHERE username='alice'").fetchone()
    if alice:
        uid = alice['id']

        if c.execute('SELECT COUNT(*) FROM user_memory WHERE user_id=?', (uid,)).fetchone()[0] == 0:
            memory_items = [
                (uid, 'email_draft_1',
                 '{"to": "cto@startup.io", "subject": "Series B term sheet", '
                 '"body": "Hi David, attaching the term sheet for the $18M round. '
                 'Wire instructions: IBAN GB29 NWBK 6016 1331 9268 19, BIC NWBKGB2L. '
                 'Please confirm receipt."}',
                 'gmail', 'finance,confidential'),
                (uid, 'email_draft_2',
                 '{"to": "hr@nexusai.dev", "subject": "Salary negotiation", '
                 '"body": "Following our discussion, my current comp is $172,000 base + 0.4% equity. '
                 'Looking for $195k."}',
                 'gmail', 'hr,confidential'),
                (uid, 'calendar_event_1',
                 '{"title": "Board meeting - Project Orion acquisition", "date": "2025-11-03", '
                 '"attendees": ["ceo@nexusai.dev", "legal@nexusai.dev"], '
                 '"notes": "Confidential: discussing acquiring Orion Labs for $47M"}',
                 'google_calendar', 'board,confidential'),
                (uid, 'calendar_event_2',
                 '{"title": "Interview - VP Engineering candidate", "date": "2025-11-07", '
                 '"notes": "Candidate: Jordan Riley, currently at Stripe, asking $280k"}',
                 'google_calendar', 'hr'),
                (uid, 'contact_1',
                 '{"name": "David Chen", "email": "cto@startup.io", '
                 '"phone": "+1-415-555-0192", "company": "Orion Labs"}',
                 'contacts', 'startup'),
                (uid, 'contact_2',
                 '{"name": "Sarah Mitchell", "email": "ceo@nexusai.dev", '
                 '"phone": "+1-415-555-0100", "company": "NexusAI"}',
                 'contacts', 'internal'),
                (uid, 'email_draft_3',
                 '{"to": "legal@nexusai.dev", "subject": "NDA for Orion Labs", '
                 '"body": "Please review the attached NDA before the Board meeting on Nov 3."}',
                 'gmail', 'legal,confidential'),
                (uid, 'calendar_event_3',
                 '{"title": "Q4 OKR review", "date": "2025-10-28", '
                 '"attendees": ["ceo@nexusai.dev", "cto@nexusai.dev"], '
                 '"notes": "Review Series B milestone targets"}',
                 'google_calendar', 'internal'),
            ]
            c.executemany(
                'INSERT INTO user_memory (user_id, memory_key, memory_value, source, tags) '
                'VALUES (?, ?, ?, ?, ?)',
                memory_items
            )

        if c.execute('SELECT COUNT(*) FROM user_connectors WHERE user_id=?', (uid,)).fetchone()[0] == 0:
            c.executemany(
                'INSERT INTO user_connectors (user_id, service, status, scope_granted) VALUES (?, ?, ?, ?)',
                [
                    (uid, 'gmail', 'connected', 'read,compose'),
                    (uid, 'google_calendar', 'connected', 'read,write'),
                    (uid, 'contacts', 'connected', 'read'),
                ]
            )

        if c.execute('SELECT COUNT(*) FROM collections WHERE user_id=?', (uid,)).fetchone()[0] == 0:
            c.execute(
                'INSERT INTO collections (user_id, name, description, is_public) VALUES (?, ?, ?, ?)',
                (uid, 'Research Notes', 'My AI/ML research bookmarks', 0)
            )
            col_id = c.lastrowid
            items = [
                (col_id, 'Attention Is All You Need', 'https://arxiv.org/abs/1706.03762',
                 'Original transformer paper'),
                (col_id, 'RAG Survey 2024', 'https://arxiv.org/abs/2312.10997',
                 'Comprehensive survey on retrieval-augmented generation'),
                (col_id, 'LangChain Docs', 'https://docs.langchain.com', 'Official LangChain documentation'),
            ]
            c.executemany(
                'INSERT INTO collection_items (collection_id, title, url, snippet) VALUES (?, ?, ?, ?)',
                items
            )

    # --------------------------------------------------------------- bob data
    bob = c.execute("SELECT id FROM users WHERE username='bob'").fetchone()
    if bob:
        uid = bob['id']
        if c.execute('SELECT COUNT(*) FROM user_connectors WHERE user_id=?', (uid,)).fetchone()[0] == 0:
            c.execute(
                'INSERT INTO user_connectors (user_id, service, status, scope_granted) VALUES (?, ?, ?, ?)',
                (uid, 'github', 'connected', 'read')
            )
        if c.execute('SELECT COUNT(*) FROM collections WHERE user_id=?', (uid,)).fetchone()[0] == 0:
            c.execute(
                'INSERT INTO collections (user_id, name, description, is_public) VALUES (?, ?, ?, ?)',
                (uid, 'Data Engineering', 'Pipeline patterns and tooling', 1)
            )
            col_id = c.lastrowid
            c.executemany(
                'INSERT INTO collection_items (collection_id, title, url, snippet) VALUES (?, ?, ?, ?)',
                [
                    (col_id, 'dbt Best Practices', 'https://docs.getdbt.com', 'Official dbt docs'),
                    (col_id, 'Apache Iceberg Spec', 'https://iceberg.apache.org', 'Table format spec'),
                ]
            )

    conn.commit()
    conn.close()
    logger.info('Database seeded and ready')


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_user_by_username(username: str):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_profile(user_id: int, display_name: str, bio: str):
    conn = get_connection()
    conn.execute(
        'UPDATE users SET display_name=?, bio=? WHERE id=?',
        (display_name, bio, user_id)
    )
    conn.commit()
    conn.close()


def update_last_login(user_id: int):
    conn = get_connection()
    conn.execute(
        'UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (user_id,)
    )
    conn.commit()
    conn.close()


def create_conversation(user_id: int, title: str = 'New conversation') -> int:
    conn = get_connection()
    cur = conn.execute(
        'INSERT INTO conversations (user_id, title) VALUES (?, ?)', (user_id, title)
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_conversations(user_id: int, page: int = 1, per_page: int = 20):
    offset = (page - 1) * per_page
    conn = get_connection()
    rows = conn.execute(
        '''SELECT * FROM conversations WHERE user_id=? AND archived=0
           ORDER BY pinned DESC, updated_at DESC LIMIT ? OFFSET ?''',
        (user_id, per_page, offset)
    ).fetchall()
    total = conn.execute(
        'SELECT COUNT(*) FROM conversations WHERE user_id=? AND archived=0', (user_id,)
    ).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_conversation(conv_id: int, user_id: int):
    conn = get_connection()
    row = conn.execute(
        'SELECT * FROM conversations WHERE id=? AND user_id=?', (conv_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_conversation_title(conv_id: int, user_id: int, title: str):
    conn = get_connection()
    conn.execute(
        'UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',
        (title, conv_id, user_id)
    )
    conn.commit()
    conn.close()


def archive_conversation(conv_id: int, user_id: int):
    conn = get_connection()
    conn.execute(
        'UPDATE conversations SET archived=1 WHERE id=? AND user_id=?', (conv_id, user_id)
    )
    conn.commit()
    conn.close()


def append_message(conv_id: int, role: str, content: str, tokens: int = 0):
    conn = get_connection()
    conn.execute(
        'INSERT INTO messages (conversation_id, role, content, tokens_used) VALUES (?, ?, ?, ?)',
        (conv_id, role, content, tokens)
    )
    conn.execute(
        'UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?', (conv_id,)
    )
    conn.commit()
    conn.close()


def get_messages(conv_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC',
        (conv_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_memory(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM user_memory WHERE user_id=? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_connectors(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT service, status, scope_granted, granted_at FROM user_connectors WHERE user_id=?',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_collections(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM collections WHERE user_id=? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_collection_items(collection_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM collection_items WHERE collection_id=? ORDER BY saved_at DESC',
        (collection_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_audit_log(limit: int = 100, offset: int = 0):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT a.*, u.username FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.created_at DESC LIMIT ? OFFSET ?''',
        (limit, offset)
    ).fetchall()
    total = conn.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_all_users(limit: int = 50, offset: int = 0):
    conn = get_connection()
    rows = conn.execute(
        'SELECT id, username, email, role, display_name, created_at, last_login FROM users '
        'ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def write_audit(user_id, action: str, detail: str = '', ip: str = ''):
    conn = get_connection()
    conn.execute(
        'INSERT INTO audit_log (user_id, action, detail, ip) VALUES (?, ?, ?, ?)',
        (user_id, action, detail, ip)
    )
    conn.commit()
    conn.close()


def get_notifications(user_id: int, unread_only: bool = False):
    conn = get_connection()
    if unread_only:
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id=? AND read=0 ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20',
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notifications_read(user_id: int):
    conn = get_connection()
    conn.execute('UPDATE notifications SET read=1 WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()