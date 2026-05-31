"""
search.py – simple full-text note search backed by SQLite LIKE queries.

For a production deployment this would be replaced with an FTS5 virtual
table or an external search engine, but LIKE is sufficient for the demo
dataset size.
"""

import logging
from db import get_db

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def search_notes(query: str, user_id: int, page: int = 1):
    """Return paginated note results matching *query* for the given user.

    Results include notes owned by *user_id* plus all public notes.
    """
    if not query or not query.strip():
        return [], 0

    term = f"%{query.strip()}%"
    offset = (max(page, 1) - 1) * PAGE_SIZE

    try:
        conn = get_db()
        total = conn.execute(
            """SELECT COUNT(*) FROM notes
               WHERE (owner_id=? OR public=1)
               AND (title LIKE ? OR body LIKE ? OR tags LIKE ?)""",
            (user_id, term, term, term),
        ).fetchone()[0]

        rows = conn.execute(
            """SELECT n.*, u.username as owner_name
               FROM notes n JOIN users u ON n.owner_id=u.id
               WHERE (n.owner_id=? OR n.public=1)
               AND (n.title LIKE ? OR n.body LIKE ? OR n.tags LIKE ?)
               ORDER BY n.updated_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, term, term, term, PAGE_SIZE, offset),
        ).fetchall()
        conn.close()
        return rows, total
    except Exception as exc:
        logger.error("search_notes error: %s", exc)
        return [], 0