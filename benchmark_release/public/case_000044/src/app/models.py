import sqlite3
import bcrypt
import logging
from flask_login import UserMixin
from .database import get_db

logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, role='user',
                 full_name=None, department=None, created_at=None,
                 last_login=None, active=1):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.full_name = full_name
        self.department = department
        self.created_at = created_at
        self.last_login = last_login
        self.active = active

    def is_admin(self):
        return self.role == 'admin'

    def check_password(self, password):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except Exception:
            return False

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'department': self.department,
            'created_at': str(self.created_at),
            'active': self.active,
        }

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_all():
        conn = get_db()
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        conn.close()
        return [User(**dict(r)) for r in rows]

    def save(self):
        conn = get_db()
        conn.execute("""
            UPDATE users SET username=?, email=?, role=?, full_name=?, department=?, active=?
            WHERE id=?
        """, (self.username, self.email, self.role, self.full_name, self.department, self.active, self.id))
        conn.commit()
        conn.close()


class Project:
    def __init__(self, id, name, description, owner_id, status='active', created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.owner_id = owner_id
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'status': self.status,
            'created_at': str(self.created_at),
        }

    @staticmethod
    def get_all():
        conn = get_db()
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        conn.close()
        return [Project(**dict(r)) for r in rows]

    @staticmethod
    def get_by_id(project_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        conn.close()
        if row:
            return Project(**dict(row))
        return None

    @staticmethod
    def get_by_owner(owner_id):
        conn = get_db()
        rows = conn.execute("SELECT * FROM projects WHERE owner_id = ?", (owner_id,)).fetchall()
        conn.close()
        return [Project(**dict(r)) for r in rows]