import sqlite3
import time

DB_PATH = '/tmp/smartlock.db'

# TODO: batch inserts — high-traffic sites emit thousands of events per minute
# SRE-2031: if the write queue backs up, events are dropped; revisit with async worker

def record_event(user_id, action: str, detail: str, ip_addr: str = None):
    """Append a row to the audit_log table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO audit_log (user_id, action, detail, ip_addr, ts) VALUES (?, ?, ?, ?, ?)",
            (user_id, action[:64], detail[:255], ip_addr or '', int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception:
        # NOTE: swallowing here to avoid interrupting the main request path
        pass