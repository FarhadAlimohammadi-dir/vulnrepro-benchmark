from db import get_db


def list_projects(owner_id: int = None, page: int = 1, per_page: int = 10):
    db = get_db()
    offset = (page - 1) * per_page
    if owner_id:
        rows = db.execute(
            '''SELECT p.*, u.username as owner_name,
                      (SELECT COUNT(*) FROM snippets s WHERE s.project_id=p.id) as snippet_count
               FROM projects p JOIN users u ON u.id=p.owner_id
               WHERE p.owner_id=? ORDER BY p.created_at DESC LIMIT ? OFFSET ?''',
            (owner_id, per_page, offset)
        ).fetchall()
        total = db.execute('SELECT COUNT(*) FROM projects WHERE owner_id=?', (owner_id,)).fetchone()[0]
    else:
        rows = db.execute(
            '''SELECT p.*, u.username as owner_name,
                      (SELECT COUNT(*) FROM snippets s WHERE s.project_id=p.id) as snippet_count
               FROM projects p JOIN users u ON u.id=p.owner_id
               WHERE p.visibility='public'
               ORDER BY p.created_at DESC LIMIT ? OFFSET ?''',
            (per_page, offset)
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM projects WHERE visibility='public'").fetchone()[0]
    return [dict(r) for r in rows], total


def get_project(project_id: int):
    db = get_db()
    row = db.execute(
        '''SELECT p.*, u.username as owner_name FROM projects p
           JOIN users u ON u.id=p.owner_id WHERE p.id=?''',
        (project_id,)
    ).fetchone()
    return dict(row) if row else None


def create_project(owner_id: int, name: str, description: str, language: str, visibility: str):
    db = get_db()
    cur = db.execute(
        'INSERT INTO projects (owner_id, name, description, language, visibility) VALUES (?,?,?,?,?)',
        (owner_id, name[:80], description[:500], language[:30],
         visibility if visibility in ('public', 'private') else 'private')
    )
    db.commit()
    return cur.lastrowid