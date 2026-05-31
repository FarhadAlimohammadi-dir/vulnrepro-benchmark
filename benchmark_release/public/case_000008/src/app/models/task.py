"""
Task model — data-access helpers for the tasks table.
"""
from datetime import datetime


def get_task(conn, task_id):
    row = conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(conn, status=None, author_id=None, label=None, limit=50, offset=0):
    query = 'SELECT * FROM tasks WHERE 1=1'
    params = []
    if status:
        query += ' AND status=?'
        params.append(status)
    if author_id:
        query += ' AND author_id=?'
        params.append(author_id)
    if label:
        query += ' AND label=?'
        params.append(label)
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params += [limit, offset]
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def create_task(conn, title, body, author_id, priority='medium', label=None):
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        '''INSERT INTO tasks
           (title, body, label, author_id, status, priority, approved, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (title, body, label, author_id, 'open', priority, 0, now, now)
    )
    conn.commit()
    return cur.lastrowid


def update_task_body(conn, task_id, title, body):
    now = datetime.utcnow().isoformat()
    conn.execute(
        'UPDATE tasks SET title=?, body=?, updated_at=? WHERE id=?',
        (title, body, now, task_id)
    )
    conn.commit()


def set_task_status(conn, task_id, status):
    now = datetime.utcnow().isoformat()
    conn.execute(
        'UPDATE tasks SET status=?, updated_at=? WHERE id=?',
        (status, now, task_id)
    )
    conn.commit()


def approve_task(conn, task_id, approver_id):
    now = datetime.utcnow().isoformat()
    conn.execute(
        '''UPDATE tasks
           SET approved=1, status='approved', approved_by=?, approved_at=?, updated_at=?
           WHERE id=?''',
        (approver_id, now, now, task_id)
    )
    conn.commit()