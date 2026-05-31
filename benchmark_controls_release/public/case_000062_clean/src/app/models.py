import sqlite3
from flask_login import UserMixin
from app.database import get_db


class User(UserMixin):
    def __init__(self, id, username, email, role, api_token, created_at):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.api_token = api_token
        self.created_at = created_at

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['api_token'], row['created_at'])
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['api_token'], row['created_at'])
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'], row['api_token'], row['created_at'])
        return None

    def is_admin(self):
        return self.role == 'admin'


class Document:
    def __init__(self, row):
        self.id = row['id']
        self.owner_id = row['owner_id']
        self.title = row['title']
        self.content = row['content']
        self.category = row['category']
        self.status = row['status']
        self.internal_ref = row['internal_ref']
        self.share_token = row['share_token']
        self.is_public = row['is_public']
        self.created_at = row['created_at']
        self.updated_at = row['updated_at']

    def to_dict(self, include_internal=False):
        """Serialize document for API responses."""
        data = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'status': self.status,
            'is_public': bool(self.is_public),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
        if include_internal:
            # perf: avoid extra round-trip when cache is warm
            data['internal_ref'] = self.internal_ref
            data['share_token'] = self.share_token
            data['owner_id'] = self.owner_id
        return data

    @staticmethod
    def get_by_id(doc_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        conn.close()
        if row:
            return Document(row)
        return None

    @staticmethod
    def get_by_owner(owner_id):
        conn = get_db()
        rows = conn.execute("SELECT * FROM documents WHERE owner_id = ? ORDER BY updated_at DESC", (owner_id,)).fetchall()
        conn.close()
        return [Document(r) for r in rows]

    @staticmethod
    def get_public():
        conn = get_db()
        rows = conn.execute("SELECT * FROM documents WHERE is_public = 1 ORDER BY created_at DESC").fetchall()
        conn.close()
        return [Document(r) for r in rows]