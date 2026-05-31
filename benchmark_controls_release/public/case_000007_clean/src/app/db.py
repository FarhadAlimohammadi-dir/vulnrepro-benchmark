import os
import sqlite3
import json

DB_PATH = os.environ.get("DB_PATH", "/data/toolforge.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            email TEXT,
            display_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        );

        CREATE TABLE IF NOT EXISTS tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            handler TEXT NOT NULL,
            config TEXT DEFAULT '{}',
            owner TEXT,
            tags TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            invoke_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS invocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT,
            invoked_by TEXT,
            args_snapshot TEXT,
            result_snippet TEXT,
            duration_ms INTEGER,
            status TEXT DEFAULT 'ok',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT,
            action TEXT,
            target TEXT,
            detail TEXT,
            ip_addr TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            owner TEXT NOT NULL,
            label TEXT,
            scopes TEXT DEFAULT 'read',
            expires_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed users
    seed_users = [
        ("admin",  "admin123",  "admin", "admin@toolforge.local",  "Administrator"),
        ("alice",  "alice456",  "user",  "alice@toolforge.local",  "Alice Martínez"),
        ("bob",    "bob789",    "user",  "bob@toolforge.local",    "Bob Nakamura"),
        ("carol",  "carol321",  "user",  "carol@toolforge.local",  "Carol Oduya"),
        ("dave",   "dave654",   "user",  "dave@toolforge.local",   "Dave Chen"),
        ("eve",    "eve987",    "user",  "eve@toolforge.local",    "Eve Larsson"),
    ]
    for uname, pwd, role, email, display in seed_users:
        try:
            conn.execute(
                "INSERT INTO users(username,password,role,email,display_name) VALUES(?,?,?,?,?)",
                (uname, pwd, role, email, display)
            )
        except sqlite3.IntegrityError:
            pass

    # Seed tools
    seed_tools = [
        ("ping_check",      "HTTP reachability probe for a remote endpoint",
         "http_fetch",      '{"method":"GET","url":"https://httpbin.org/get"}',
         "admin",           "network,ops"),
        ("read_readme",     "Read the workspace README file",
         "read_file",       '{"path":"/app/README.md"}',
         "admin",           "docs"),
        ("greet_user",      "Render a personalised greeting message",
         "template_render", '{"template":"Hello, {{ name }}! Welcome to ToolForge."}',
         "admin",           "util"),
        ("env_summary",     "Render a text summary from provided key-value pairs",
         "template_render", '{"template":"Environment: {{ env }} | Region: {{ region }}"}',
         "alice",           "ops,util"),
        ("status_fetch",    "Fetch the public status page for a service",
         "http_fetch",      '{"method":"GET","url":"https://status.github.com/"}',
         "alice",           "ops,monitoring"),
        ("workspace_info",  "Return the workspace root directory listing file",
         "read_file",       '{"path":"/app/README.md"}',
         "bob",             "docs"),
        ("motd_render",     "Render the message-of-the-day banner",
         "template_render", '{"template":"[{{ date }}] Notice: {{ message }}"}',
         "bob",             "util"),
        ("health_fetch",    "Probe the internal health endpoint",
         "http_fetch",      '{"method":"GET","url":"https://httpbin.org/status/200"}',
         "carol",           "monitoring"),
        ("report_render",   "Generate a plain-text incident report snippet",
         "template_render", '{"template":"Incident {{ id }}: {{ title }}\\nSeverity: {{ severity }}"}',
         "carol",           "ops"),
        ("manifest_read",   "Read the tool manifest file",
         "read_file",       '{"path":"/app/README.md"}',
         "dave",            "docs"),
    ]
    for name, desc, handler, cfg, owner, tags in seed_tools:
        try:
            conn.execute(
                "INSERT INTO tools(name,description,handler,config,owner,tags) VALUES(?,?,?,?,?,?)",
                (name, desc, handler, cfg, owner, tags)
            )
        except sqlite3.IntegrityError:
            pass

    # Seed audit log
    seed_audit = [
        ("admin", "user.created", "alice",       "Initial seed"),
        ("admin", "user.created", "bob",         "Initial seed"),
        ("admin", "tool.created", "ping_check",  "Initial seed"),
        ("admin", "tool.created", "read_readme", "Initial seed"),
        ("alice", "tool.invoked", "ping_check",  "Manual test"),
        ("bob",   "tool.invoked", "greet_user",  "Demo run"),
    ]
    for actor, action, target, detail in seed_audit:
        try:
            conn.execute(
                "INSERT INTO audit_log(actor,action,target,detail,ip_addr) VALUES(?,?,?,?,?)",
                (actor, action, target, detail, "127.0.0.1")
            )
        except Exception:
            pass

    conn.commit()
    conn.close()