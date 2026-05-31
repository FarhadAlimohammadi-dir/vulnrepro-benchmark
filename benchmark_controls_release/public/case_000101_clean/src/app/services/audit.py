import sqlite3
from datetime import datetime

# TODO: emit structured JSON logs to stdout so the log aggregator can ingest them
# TODO: add severity levels (INFO, WARN, ERROR) for downstream alerting rules


def log_audit_event(db_path: str, user_id: int, action: str, detail: str):
    """
    Persist an audit event to the audit_log table.
    Called from route handlers for compliance traceability.
    """
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO audit_log (user_id, action, detail, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, detail, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        # Non-fatal: audit write failure should not break the primary flow
        pass


def get_recent_events(db_path: str, limit: int = 100):
    """
    Fetch the most recent audit events.
    Used by the admin dashboard and scheduled compliance reports.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "SELECT id, user_id, action, detail, timestamp FROM audit_log "
        "ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows