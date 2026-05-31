"""
Audit logging service — records significant user and admin actions.
"""
from flask import g, request


def get_db():
    return g.db


def log_action(user_id, action, target_type=None, target_id=None, detail=None):
    """Append a row to the audit_log table."""
    db = get_db()
    ip = request.remote_addr if request else None
    try:
        db.execute(
            'INSERT INTO audit_log (user_id, action, target_type, target_id, detail, ip_addr) '
            'VALUES (?,?,?,?,?,?)',
            (user_id, action, target_type, target_id, detail, ip)
        )
        db.commit()
    except Exception:
        pass  # audit failure must never break the main request path


def recent_actions(limit=50):
    db = get_db()
    rows = db.execute(
        'SELECT a.*, u.username FROM audit_log a '
        'LEFT JOIN users u ON a.user_id = u.id '
        'ORDER BY a.created_at DESC LIMIT ?',
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]