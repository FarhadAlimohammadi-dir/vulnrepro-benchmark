import time

# TODO: consider streaming audit events to Kafka for real-time SIEM integration

def record_event(conn, user_id, action, detail, ip):
    """Append an audit entry.  Called on every state-changing request."""
    ts = int(time.time())
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO audit_log (user_id, action, detail, ip, ts) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, str(detail)[:500], str(ip)[:64], ts)
        )
        conn.commit()
    except Exception:
        # NOTE: audit failures must never break the primary request path
        pass