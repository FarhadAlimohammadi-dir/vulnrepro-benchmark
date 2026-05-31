"""
Image import job tracker.
Wraps job lifecycle: creation, status polling, cancellation.

TODO: wire up real GCP Daisy workflow API calls (PLAT-1055)
TODO: add exponential backoff for transient GCP API errors (SRE-2100)
"""

import time

TERMINAL_STATES = {'done', 'failed', 'cancelled'}

def create_job_record(conn, username, image_name, source_image, bucket_name):
    """Insert a new import job and return its row id."""
    now = int(time.time())
    cur = conn.execute(
        '''INSERT INTO image_jobs (username, image_name, source_image, status, created_at, bucket_name)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (username, image_name, source_image, 'pending', now, bucket_name)
    )
    conn.commit()
    return cur.lastrowid

def get_job(conn, job_id, username, role='user'):
    """Fetch a single job, enforcing ownership for non-admins."""
    if role == 'admin':
        return conn.execute('SELECT * FROM image_jobs WHERE id=?', (job_id,)).fetchone()
    return conn.execute(
        'SELECT * FROM image_jobs WHERE id=? AND username=?', (job_id, username)
    ).fetchone()

def cancel_job(conn, job_id, username, role='user'):
    """
    Mark a pending/running job as cancelled.
    Returns True on success, False if job not found or already terminal.
    """
    job = get_job(conn, job_id, username, role)
    if not job:
        return False
    if job['status'] in TERMINAL_STATES:
        return False
    conn.execute("UPDATE image_jobs SET status='cancelled' WHERE id=?", (job_id,))
    conn.commit()
    return True

def summarize_jobs(conn, username, role='user'):
    """Return a status-count summary for dashboard widgets."""
    if role == 'admin':
        rows = conn.execute(
            'SELECT status, COUNT(*) as cnt FROM image_jobs GROUP BY status'
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT status, COUNT(*) as cnt FROM image_jobs WHERE username=? GROUP BY status',
            (username,)
        ).fetchall()
    return {r['status']: r['cnt'] for r in rows}