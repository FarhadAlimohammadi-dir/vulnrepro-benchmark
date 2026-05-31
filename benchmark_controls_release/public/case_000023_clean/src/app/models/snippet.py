from db import get_db


def list_snippets(owner_id: int = None, page: int = 1, per_page: int = 15, search: str = None):
    db = get_db()
    offset = (page - 1) * per_page
    where_clauses = []
    params = []

    if owner_id is not None:
        where_clauses.append('s.owner_id=?')
        params.append(owner_id)

    if search:
        where_clauses.append('(s.title LIKE ? OR s.description LIKE ? OR s.tags LIKE ?)')
        like = f'%{search}%'
        params.extend([like, like, like])

    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    rows = db.execute(
        f'''SELECT s.id, s.title, s.language, s.tags, s.view_count,
                   s.created_at, u.username as owner_name
            FROM snippets s
            JOIN users u ON u.id = s.owner_id
            {where_sql}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?''',
        params + [per_page, offset]
    ).fetchall()

    count_row = db.execute(
        f'SELECT COUNT(*) FROM snippets s {where_sql}', params
    ).fetchone()
    total = count_row[0] if count_row else 0
    return [dict(r) for r in rows], total


def get_snippet(snippet_id: int, owner_id: int = None):
    db = get_db()
    if owner_id:
        row = db.execute(
            'SELECT * FROM snippets WHERE id=? AND owner_id=?',
            (snippet_id, owner_id)
        ).fetchone()
    else:
        row = db.execute('SELECT * FROM snippets WHERE id=?', (snippet_id,)).fetchone()
    return dict(row) if row else None


def create_snippet(owner_id: int, title: str, language: str, code: str,
                   description: str = '', tags: str = '', project_id: int = None):
    db = get_db()
    cur = db.execute(
        '''INSERT INTO snippets (owner_id, project_id, title, language, code, description, tags)
           VALUES (?,?,?,?,?,?,?)''',
        (owner_id, project_id, title[:120], language[:30], code, description[:500], tags[:200])
    )
    db.commit()
    return cur.lastrowid


def update_snippet(snippet_id: int, owner_id: int, title: str, language: str,
                   code: str, description: str, tags: str):
    db = get_db()
    db.execute(
        '''UPDATE snippets SET title=?, language=?, code=?, description=?, tags=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=? AND owner_id=?''',
        (title[:120], language[:30], code, description[:500], tags[:200], snippet_id, owner_id)
    )
    db.commit()


def delete_snippet(snippet_id: int, owner_id: int):
    db = get_db()
    db.execute('DELETE FROM snippets WHERE id=? AND owner_id=?', (snippet_id, owner_id))
    db.commit()


def increment_views(snippet_id: int):
    db = get_db()
    db.execute('UPDATE snippets SET view_count = view_count + 1 WHERE id=?', (snippet_id,))
    db.commit()