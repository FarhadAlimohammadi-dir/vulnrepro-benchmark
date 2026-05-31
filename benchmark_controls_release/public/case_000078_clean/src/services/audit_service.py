"""
AuditService — thin wrapper around audit_log writes.
TODO: add severity levels (INFO / WARN / CRITICAL) for SIEM integration.
"""
import sqlite3

DB_PATH = "/tmp/filesync.db"


def log_event(user_id: int, action: str, detail: str, ip: str, severity: str = "INFO") -> None:
    """
    Persists an audit event.  severity is reserved for future SIEM routing
    and not yet stored in the schema (schema migration pending).
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO audit_log (user_id, action, detail, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, action, detail, ip)
        )
        conn.commit()
        conn.close()
    except Exception:
        # NOTE: swallowing here so audit failures never break the request path
        pass


def recent_events(limit: int = 50) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT a.id, u.username, a.action, a.detail, a.ip_address, a.created_at
                 FROM audit_log a LEFT JOIN users u ON a.user_id=u.id
                 ORDER BY a.id DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "action": r[2],
             "detail": r[3], "ip": r[4], "timestamp": r[5]} for r in rows]