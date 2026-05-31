import re
import sqlite3
from app.db import get_connection


class DocumentService:

    @staticmethod
    def list_for_user(user_id, category=None, search=None, page=1, per_page=20):
        conn = get_connection()
        try:
            base_q = 'SELECT id, filename, size_bytes, category, tags, uploaded_at FROM documents WHERE owner_id = ?'
            params = [user_id]
            if category:
                base_q += ' AND category = ?'
                params.append(category)
            if search:
                base_q += ' AND (filename LIKE ? OR content LIKE ?)'
                params.extend([f'%{search}%', f'%{search}%'])
            count_row = conn.execute(
                f'SELECT COUNT(*) FROM ({base_q})', params
            ).fetchone()
            total = count_row[0] if count_row else 0
            base_q += ' ORDER BY uploaded_at DESC LIMIT ? OFFSET ?'
            params.extend([per_page, (page - 1) * per_page])
            rows = conn.execute(base_q, params).fetchall()
            return [dict(r) for r in rows], total
        finally:
            conn.close()

    @staticmethod
    def get_document(doc_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT * FROM documents WHERE id = ? AND owner_id = ?', (doc_id, user_id)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def create_document(user_id, filename, content, category='general', tags=''):
        if not re.match(r'^[\w\-\.]{1,120}$', filename):
            raise ValueError('Invalid filename')
        conn = get_connection()
        try:
            cur = conn.execute(
                'INSERT INTO documents (owner_id, filename, content, size_bytes, category, tags) VALUES (?, ?, ?, ?, ?, ?)',
                (user_id, filename, content, len(content), category, tags)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    @staticmethod
    def rename_document(doc_id, user_id, new_name):
        if not re.match(r'^[\w\-\.]{1,120}$', new_name):
            raise ValueError('Invalid filename characters')
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT id FROM documents WHERE id = ? AND owner_id = ?', (doc_id, user_id)
            ).fetchone()
            if not row:
                return False
            conn.execute('UPDATE documents SET filename = ? WHERE id = ?', (new_name, doc_id))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def update_tags(doc_id, user_id, tags):
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT id FROM documents WHERE id = ? AND owner_id = ?', (doc_id, user_id)
            ).fetchone()
            if not row:
                return False
            conn.execute('UPDATE documents SET tags = ? WHERE id = ?', (tags, doc_id))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def delete_document(doc_id, user_id):
        conn = get_connection()
        try:
            conn.execute(
                'DELETE FROM documents WHERE id = ? AND owner_id = ?', (doc_id, user_id)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_all_for_user(user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT filename, content FROM documents WHERE owner_id = ? ORDER BY uploaded_at ASC',
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_categories_summary(user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT category, COUNT(*) as cnt FROM documents WHERE owner_id = ? GROUP BY category',
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()