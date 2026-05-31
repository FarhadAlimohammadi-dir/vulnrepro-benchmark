from db import get_db


def log_action(user_id, action: str, resource_type: str = None,
               resource_id: int = None, detail: str = None, ip: str = None):
    try:
        db = get_db()
        db.execute(
            '''INSERT INTO audit_log (user_id, action, resource_type, resource_id, detail, ip_address)
               VALUES (?,?,?,?,?,?)''',
            (user_id, action, resource_type, resource_id, detail, ip)
        )
        db.commit()
    except Exception:
        pass  # audit failures must not break the main request path


def get_recent_logs(limit: int = 50, user_id: int = None):
    db = get_db()
    if user_id:
        rows = db.execute(
            '''SELECT a.*, u.username FROM audit_log a
               LEFT JOIN users u ON u.id=a.user_id
               WHERE a.user_id=? ORDER BY a.created_at DESC LIMIT ?''',
            (user_id, limit)
        ).fetchall()
    else:
        rows = db.execute(
            '''SELECT a.*, u.username FROM audit_log a
               LEFT JOIN users u ON u.id=a.user_id
               ORDER BY a.created_at DESC LIMIT ?''',
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]