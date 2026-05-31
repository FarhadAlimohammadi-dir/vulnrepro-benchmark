"""
Audit log model — write-once append for compliance tracking.
"""
from datetime import datetime


def log_event(conn, actor_id, actor_name, action, resource, detail='', ip=''):
    now = datetime.utcnow().isoformat()
    conn.execute(
        '''INSERT INTO audit_log
           (actor_id, actor_name, action, resource, detail, ip_address, created_at)
           VALUES (?,?,?,?,?,?,?)''',
        (actor_id, actor_name, action, resource, detail, ip, now)
    )
    conn.commit()


def recent_events(conn, limit=100, offset=0, actor_name=None, action=None):
    query = 'SELECT * FROM audit_log WHERE 1=1'
    params = []
    if actor_name:
        query += ' AND actor_name=?'
        params.append(actor_name)
    if action:
        query += ' AND action LIKE ?'
        params.append(f'%{action}%')
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params += [limit, offset]
    return [dict(r) for r in conn.execute(query, params).fetchall()]