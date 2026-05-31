"""
Notification service — creates in-app notifications for users.
"""
from datetime import datetime


def notify(conn, user_id, message):
    now = datetime.utcnow().isoformat()
    conn.execute(
        'INSERT INTO notifications (user_id, message, read, created_at) VALUES (?,?,?,?)',
        (user_id, message, 0, now)
    )
    conn.commit()


def get_unread(conn, user_id):
    rows = conn.execute(
        '''SELECT * FROM notifications
           WHERE user_id=? AND read=0
           ORDER BY created_at DESC''',
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def mark_read(conn, user_id, notification_id):
    conn.execute(
        'UPDATE notifications SET read=1 WHERE id=? AND user_id=?',
        (notification_id, user_id)
    )
    conn.commit()