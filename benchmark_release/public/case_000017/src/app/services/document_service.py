"""
Document service — CRUD, search, and content access helpers.
"""
import re
import sqlite3
from flask import g


def get_db():
    return g.db


def list_documents(page=1, per_page=10, tag=None):
    db = get_db()
    offset = (page - 1) * per_page
    if tag:
        rows = db.execute(
            'SELECT d.*, u.username as owner_name FROM documents d '
            'LEFT JOIN users u ON d.owner_id = u.id '
            'WHERE d.tags = ? ORDER BY d.updated_at DESC LIMIT ? OFFSET ?',
            (tag, per_page, offset)
        ).fetchall()
        total = db.execute(
            'SELECT COUNT(*) FROM documents WHERE tags = ?', (tag,)
        ).fetchone()[0]
    else:
        rows = db.execute(
            'SELECT d.*, u.username as owner_name FROM documents d '
            'LEFT JOIN users u ON d.owner_id = u.id '
            'ORDER BY d.updated_at DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
        total = db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    return [dict(r) for r in rows], total


def get_document(doc_id):
    db = get_db()
    row = db.execute(
        'SELECT d.*, u.username as owner_name FROM documents d '
        'LEFT JOIN users u ON d.owner_id = u.id WHERE d.id = ?',
        (doc_id,)
    ).fetchone()
    return dict(row) if row else None


def create_document(title, body, owner_id, tags='', is_shared=True):
    db = get_db()
    cur = db.execute(
        'INSERT INTO documents (title, body, owner_id, tags, is_shared) VALUES (?,?,?,?,?)',
        (title, body, owner_id, tags, 1 if is_shared else 0)
    )
    db.commit()
    return cur.lastrowid


def update_document(doc_id, title, body, tags=''):
    db = get_db()
    db.execute(
        'UPDATE documents SET title=?, body=?, tags=?, version=version+1, '
        'updated_at=CURRENT_TIMESTAMP WHERE id=?',
        (title, body, tags, doc_id)
    )
    db.commit()


def delete_document(doc_id):
    db = get_db()
    db.execute('DELETE FROM documents WHERE id=?', (doc_id,))
    db.commit()


def search_documents(query, limit=10):
    """Full-text search across title and body fields."""
    db = get_db()
    # Sanitize query before embedding in LIKE clause
    safe_q = re.sub(r'[\x00-\x1f\x7f%_]', '', query)[:200]
    pattern = f'%{safe_q}%'
    rows = db.execute(
        'SELECT d.id, d.title, d.body, d.tags, d.updated_at, u.username as owner_name '
        'FROM documents d LEFT JOIN users u ON d.owner_id = u.id '
        'WHERE d.title LIKE ? OR d.body LIKE ? LIMIT ?',
        (pattern, pattern, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def strip_markdown(text):
    """Return plain-text version of a markdown document for safe display."""
    # Remove image syntax
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    # Remove link syntax, keep display text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove emphasis, code, heading markers
    text = re.sub(r'[*_`#>~]', '', text)
    # Collapse whitespace
    return ' '.join(text.split())


def safe_preview(doc, chars=150):
    """Return a short, display-safe preview of document body."""
    plain = strip_markdown(doc.get('body', ''))
    if len(plain) <= chars:
        return plain
    return plain[:chars].rsplit(' ', 1)[0] + '…'