"""
Workflow model — helpers for generated_workflows table.
"""
from datetime import datetime


def get_workflow(conn, wf_id):
    row = conn.execute(
        'SELECT * FROM generated_workflows WHERE id=?', (wf_id,)
    ).fetchone()
    return dict(row) if row else None


def list_workflows(conn, task_id=None, limit=50, offset=0):
    query = 'SELECT * FROM generated_workflows WHERE 1=1'
    params = []
    if task_id is not None:
        query += ' AND task_id=?'
        params.append(task_id)
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params += [limit, offset]
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def save_workflow(conn, task_id, yaml_content, agent_version='2.1'):
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        '''INSERT INTO generated_workflows
           (task_id, yaml_content, agent_version, created_at)
           VALUES (?,?,?,?)''',
        (task_id, yaml_content, agent_version, now)
    )
    conn.commit()
    return cur.lastrowid