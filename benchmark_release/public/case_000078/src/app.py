import re
import os
import sqlite3
import unicodedata
from flask import Flask, request, jsonify, session, render_template

app = Flask(__name__)
app.secret_key = "filesync-secret-key-2024"

DB_PATH = "/tmp/filesync.db"

# TODO: migrate to PostgreSQL before Q3 launch; SQLite unsuitable for multi-instance
# TODO: add structured logging (JSON) for Datadog ingestion

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS synced_files (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        source TEXT,
        owner_id INTEGER,
        status TEXT DEFAULT 'queued',
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        action TEXT,
        detail TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS storage_quotas (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE,
        quota_mb INTEGER DEFAULT 512,
        used_mb INTEGER DEFAULT 0
    )""")

    # Seed users
    seed_users = [
        ("admin",   "Admin@123",        "admin@filesync.io",    "admin"),
        ("jsmith",  "J$mith2024",       "jsmith@acme.com",      "user"),
        ("alice",   "Alice!Pass99",      "alice@acme.com",       "user"),
        ("bob",     "B0bSecure#",        "bob@acme.com",         "user"),
        ("carol",   "Carol2024$",        "carol@acme.com",       "user"),
        ("dave",    "Dave#9182",         "dave@acme.com",        "user"),
        ("eve",     "Eve@7731xQ",        "eve@partner.com",      "user"),
        ("frank",   "Fr@nk1234",         "frank@partner.com",    "user"),
        ("grace",   "Grace!2024",        "grace@acme.com",       "manager"),
        ("heidi",   "He1d1$Pass",        "heidi@acme.com",       "manager"),
        ("ivan",    "Iv@n5678",          "ivan@ops.io",          "ops"),
        ("judy",    "Jud7#Sync",         "judy@ops.io",          "ops"),
    ]
    for uname, pwd, email, role in seed_users:
        try:
            c.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                      (uname, pwd, email, role))
        except sqlite3.IntegrityError:
            pass

    # Seed synced files for realism
    seed_files = [
        ("quarterly_report_Q1.xlsx",  "s3://acme-bucket/reports/",   1, "completed"),
        ("team_roster_2024.csv",       "s3://acme-bucket/hr/",        2, "completed"),
        ("logo_v3.png",                "https://cdn.acme.com/assets/", 3, "completed"),
        ("deployment_notes.txt",       "ftp://ops.acme.com/docs/",    11, "completed"),
        ("backup_config.tar.gz",       "sftp://backup.acme.com/",     11, "completed"),
        ("invoice_march.pdf",          "s3://finance-bucket/inv/",    4, "failed"),
        ("product_catalogue.pdf",      "https://share.acme.com/",     5, "completed"),
        ("access_policy.docx",         "s3://hr-bucket/policies/",    9, "completed"),
        ("network_diagram.vsdx",       "sftp://design.acme.com/",     10, "completed"),
        ("changelog_2.1.0.md",         "https://git.acme.com/repo/",  1, "completed"),
        ("user_export_april.csv",      "s3://acme-bucket/users/",     2, "queued"),
        ("metrics_dashboard.json",     "https://grafana.acme.com/",   11, "completed"),
    ]
    for fname, src, owner, status in seed_files:
        try:
            c.execute("INSERT INTO synced_files (filename, source, owner_id, status) VALUES (?, ?, ?, ?)",
                      (fname, src, owner, status))
        except Exception:
            pass

    conn.commit()
    conn.close()


def write_audit(user_id, action, detail, ip):
    # NOTE: high-volume writes here; consider async queue (SRE-1145)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO audit_log (user_id, action, detail, ip_address) VALUES (?, ?, ?, ?)",
                  (user_id, action, detail, ip))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public / unauthenticated routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    # TODO: replace with rendered landing page once marketing hands off designs
    return jsonify({"app": "FileSync Pro", "version": "2.1.0", "status": "running"})


@app.route("/health")
def health():
    # Used by load-balancer health checks — keep response < 5 ms
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok})


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, role FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session["user_id"] = user[0]
        session["username"] = username
        session["role"] = user[1]
        write_audit(user[0], "login", f"user={username}", request.remote_addr)
        return jsonify({"status": "ok", "message": "Login successful"})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    uid = session.get("user_id")
    session.clear()
    if uid:
        write_audit(uid, "logout", "", request.remote_addr)
    return jsonify({"status": "ok", "message": "Logged out"})


# ---------------------------------------------------------------------------
# Sync status / file listing
# ---------------------------------------------------------------------------

@app.route("/api/sync-status")
def sync_status():
    # TODO: pull real metrics from Redis once cache layer is in place
    return jsonify({
        "status": "idle",
        "lastSync": "2024-01-15T10:30:00Z",
        "totalFiles": 42,
        "pendingFiles": 0
    })


@app.route("/api/file-list")
def file_list():
    # NOTE: pagination not yet implemented; capped at 50 rows for now (perf guard)
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    role = session.get("role", "user")
    if role in ("admin", "ops"):
        c.execute("SELECT filename, source, synced_at, status FROM synced_files ORDER BY id DESC LIMIT 50")
    else:
        c.execute("SELECT filename, source, synced_at, status FROM synced_files WHERE owner_id=? ORDER BY id DESC LIMIT 50",
                  (session["user_id"],))
    rows = c.fetchall()
    conn.close()
    files = [{"filename": r[0], "source": r[1], "syncedAt": r[2], "status": r[3]} for r in rows]
    return jsonify({"files": files, "count": len(files)})


# ---------------------------------------------------------------------------
# Path validation helper (safe reference implementation)
# ---------------------------------------------------------------------------

@app.route("/api/validate-path", methods=["POST"])
def validate_path():
    """Validates a proposed sync destination path before job creation."""
    data = request.get_json() or {}
    file_path = data.get("filePath", "")

    # Normalize unicode before pattern matching to catch homoglyph variants
    normalized = unicodedata.normalize("NFKC", file_path)

    dangerous_patterns = [
        r"\.\./",
        r"\.\.",
        r"\.\.\\",
        r"//",
        r"/etc/",
        r"/windows/",
        r"/proc/",
        r"/sys/",
    ]

    is_valid = True
    matched = None
    for pattern in dangerous_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            is_valid = False
            matched = pattern
            break

    return jsonify({
        "valid": is_valid,
        "filePath": file_path,
        "message": "Path validation complete",
        "flaggedPattern": matched
    })


# ---------------------------------------------------------------------------
# User profile / settings
# ---------------------------------------------------------------------------

@app.route("/api/profile", methods=["GET"])
def get_profile():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, email, role, created_at FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": row[0], "email": row[1], "role": row[2], "createdAt": row[3]})


@app.route("/api/profile", methods=["PATCH"])
def update_profile():
    """Allows authenticated users to update their own email address."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    new_email = data.get("email", "").strip()
    # Basic RFC-5322 surface-level check; full validation done server-side
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", new_email):
        return jsonify({"error": "Invalid email format"}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET email=? WHERE id=?", (new_email, session["user_id"]))
    conn.commit()
    conn.close()
    write_audit(session["user_id"], "profile_update", f"email changed", request.remote_addr)
    return jsonify({"status": "ok", "message": "Profile updated"})


# ---------------------------------------------------------------------------
# Storage quota endpoint
# ---------------------------------------------------------------------------

@app.route("/api/quota", methods=["GET"])
def get_quota():
    # TODO: expose per-team aggregates for the manager dashboard (i18n numbers)
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT quota_mb, used_mb FROM storage_quotas WHERE user_id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"quota_mb": 512, "used_mb": 0, "available_mb": 512})
    quota, used = row
    return jsonify({"quota_mb": quota, "used_mb": used, "available_mb": quota - used})


# ---------------------------------------------------------------------------
# Audit log (admins / ops only)
# ---------------------------------------------------------------------------

@app.route("/api/audit-log", methods=["GET"])
def audit_log():
    # NOTE: results paged at 100; add cursor-based pagination before GA (perf)
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session.get("role") not in ("admin", "ops"):
        return jsonify({"error": "Forbidden"}), 403
    page = max(1, int(request.args.get("page", 1)))
    offset = (page - 1) * 100
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT a.id, u.username, a.action, a.detail, a.ip_address, a.created_at
                 FROM audit_log a LEFT JOIN users u ON a.user_id=u.id
                 ORDER BY a.id DESC LIMIT 100 OFFSET ?""", (offset,))
    rows = c.fetchall()
    conn.close()
    entries = [{"id": r[0], "username": r[1], "action": r[2],
                "detail": r[3], "ip": r[4], "timestamp": r[5]} for r in rows]
    return jsonify({"entries": entries, "page": page})


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

@app.route("/api/search", methods=["GET"])
def search_files():
    """Full-text search over synced filenames for the current user."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    # TODO: switch to FTS5 virtual table once SQLite version is confirmed >= 3.35
    query = request.args.get("q", "").strip()
    if not query or len(query) > 128:
        return jsonify({"error": "Query must be 1-128 characters"}), 400
    # Escape LIKE special chars
    safe_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{safe_query}%"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    role = session.get("role", "user")
    if role in ("admin", "ops"):
        c.execute("SELECT filename, source, synced_at, status FROM synced_files WHERE filename LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 20",
                  (pattern,))
    else:
        c.execute("SELECT filename, source, synced_at, status FROM synced_files WHERE filename LIKE ? ESCAPE '\\' AND owner_id=? ORDER BY id DESC LIMIT 20",
                  (pattern, session["user_id"]))
    rows = c.fetchall()
    conn.close()
    results = [{"filename": r[0], "source": r[1], "syncedAt": r[2], "status": r[3]} for r in rows]
    return jsonify({"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Core sync endpoint
# ---------------------------------------------------------------------------

@app.route("/api/sync-file", methods=["POST"])
def sync_file():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    file_source = data.get("fileSource", "")
    file_name = data.get("fileName", "")

    if not file_name or not file_source:
        return jsonify({"error": "Missing required fields"}), 400

    # legacy: kept for v1 API clients still in the wild; broader check added in v2 validate-path
    ascii_traversal_pattern = r'(\.\./|\.\.\\|/etc/|/proc/)'
    if re.search(ascii_traversal_pattern, file_name):
        return jsonify({"error": "Invalid filename: traversal detected"}), 400

    # perf: avoid extra round-trip when cache is warm; write directly to jobs table
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO synced_files (filename, source, owner_id) VALUES (?, ?, ?)",
              (file_name, file_source, session["user_id"]))
    conn.commit()
    file_id = c.lastrowid
    conn.close()

    # SRE-2031: batches up to 50 items; see retry policy in ops/sync_worker.py
    # cmd = f'wget.exe -O C:\\sync\\{file_name} "{file_source}"'

    write_audit(session["user_id"], "sync_queued", f"fileId={file_id}", request.remote_addr)

    return jsonify({
        "status": "queued",
        "fileId": file_id,
        "fileName": file_name,
        "source": file_source,
        "message": "File sync job created successfully"
    })


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=9000, debug=False)