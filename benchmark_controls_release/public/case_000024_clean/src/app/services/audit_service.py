"""
Audit log service — records user actions for compliance and debugging.
"""
from db import get_db


def log_action(user_id, action, resource_type=None, resource_id=None, detail=None, ip=None):
    """Append an entry to the audit log table."""
    try:
        db = get_db()
        db.execute(
            'INSERT INTO audit_log '
            '(user_id, action, resource_type, resource_id, detail, ip_address) '
            'VALUES (?,?,?,?,?,?)',
            (user_id, action, resource_type, resource_id, detail, ip)
        )
        db.commit()
    except Exception:
        pass  # Audit failures must not disrupt the request path


def get_recent_log(limit=100):
    db = get_db()
    return db.execute(
        'SELECT al.id, al.action, al.resource_type, al.resource_id, '
        '       al.detail, al.ip_address, al.created_at, u.username '
        'FROM audit_log al LEFT JOIN users u ON al.user_id=u.id '
        'ORDER BY al.created_at DESC LIMIT ?',
        (limit,)
    ).fetchall()


def get_user_log(user_id, limit=50):
    db = get_db()
    return db.execute(
        'SELECT id, action, resource_type, resource_id, detail, created_at '
        'FROM audit_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()