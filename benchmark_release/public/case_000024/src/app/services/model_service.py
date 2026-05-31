"""
Business-logic layer for model records.
Keeps route handlers thin and makes unit-testing easier.
"""
import json
import os
import re
from datetime import datetime

from db import get_db


def sanitize_name(name: str) -> str:
    """Strip characters not suitable for a model identifier."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '', name)[:64]


def list_public_models(page: int = 1, per_page: int = 15, search: str = ''):
    db = get_db()
    offset = (page - 1) * per_page
    if search:
        pattern = f'%{search}%'
        rows = db.execute(
            'SELECT m.id, m.name, m.framework, m.status, m.description, '
            '       m.download_count, m.created_at, u.username '
            'FROM models m JOIN users u ON m.owner_id=u.id '
            'WHERE m.is_public=1 AND (m.name LIKE ? OR m.description LIKE ?) '
            'ORDER BY m.created_at DESC LIMIT ? OFFSET ?',
            (pattern, pattern, per_page, offset)
        ).fetchall()
        total = db.execute(
            'SELECT COUNT(*) FROM models m WHERE m.is_public=1 '
            'AND (m.name LIKE ? OR m.description LIKE ?)',
            (pattern, pattern)
        ).fetchone()[0]
    else:
        rows = db.execute(
            'SELECT m.id, m.name, m.framework, m.status, m.description, '
            '       m.download_count, m.created_at, u.username '
            'FROM models m JOIN users u ON m.owner_id=u.id '
            'WHERE m.is_public=1 '
            'ORDER BY m.created_at DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
        total = db.execute(
            'SELECT COUNT(*) FROM models WHERE is_public=1'
        ).fetchone()[0]
    return rows, total


def get_model_by_id(model_id: int):
    db = get_db()
    return db.execute(
        'SELECT m.*, u.username FROM models m '
        'JOIN users u ON m.owner_id=u.id WHERE m.id=?',
        (model_id,)
    ).fetchone()


def can_view_model(model, user_id: int, role: str = 'user') -> bool:
    return bool(
        model and (
            model['is_public'] or
            model['owner_id'] == user_id or
            role == 'admin'
        )
    )


def get_user_models(user_id: int):
    db = get_db()
    return db.execute(
        'SELECT m.id, m.name, m.framework, m.status, m.description, '
        '       m.download_count, m.created_at '
        'FROM models m WHERE m.owner_id=? ORDER BY m.created_at DESC',
        (user_id,)
    ).fetchall()


def create_model_record(name, framework, owner_id, file_path, config_summary, description=''):
    db = get_db()
    cur = db.execute(
        'INSERT INTO models (name, framework, owner_id, file_path, config_summary, '
        '                    description, status) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (name, framework, owner_id, file_path,
         json.dumps(config_summary), description, 'ready')
    )
    db.commit()
    return cur.lastrowid


def delete_model(model_id: int, user_id: int, role: str):
    db = get_db()
    model = db.execute('SELECT * FROM models WHERE id=?', (model_id,)).fetchone()
    if not model:
        return False, 'Not found'
    if model['owner_id'] != user_id and role != 'admin':
        return False, 'Forbidden'
    if model['file_path'] and os.path.exists(model['file_path']):
        try:
            os.remove(model['file_path'])
        except OSError:
            pass
    db.execute('DELETE FROM models WHERE id=?', (model_id,))
    db.execute('DELETE FROM tags WHERE model_id=?', (model_id,))
    db.commit()
    return True, 'Deleted'


def increment_download(model_id: int):
    db = get_db()
    db.execute(
        'UPDATE models SET download_count=download_count+1 WHERE id=?',
        (model_id,)
    )
    db.commit()


def get_tags(model_id: int):
    db = get_db()
    return [r['tag'] for r in
            db.execute('SELECT tag FROM tags WHERE model_id=?', (model_id,)).fetchall()]


def set_tags(model_id: int, tags: list):
    db = get_db()
    db.execute('DELETE FROM tags WHERE model_id=?', (model_id,))
    for t in tags[:10]:
        t = re.sub(r'[^a-zA-Z0-9\-_]', '', t)[:30]
        if t:
            db.execute('INSERT INTO tags (model_id, tag) VALUES (?,?)', (model_id, t))
    db.commit()


def get_comments(model_id: int):
    db = get_db()
    return db.execute(
        'SELECT c.id, c.body, c.created_at, u.username '
        'FROM comments c JOIN users u ON c.user_id=u.id '
        'WHERE c.model_id=? ORDER BY c.created_at ASC',
        (model_id,)
    ).fetchall()


def add_comment(model_id: int, user_id: int, body: str):
    body = body.strip()[:2000]
    if not body:
        return False
    db = get_db()
    db.execute(
        'INSERT INTO comments (model_id, user_id, body) VALUES (?,?,?)',
        (model_id, user_id, body)
    )
    db.commit()
    return True
