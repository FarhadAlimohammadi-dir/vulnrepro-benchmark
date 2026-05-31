from flask_login import UserMixin
from app import get_db
import logging

logger = logging.getLogger("cloudpanel.models")


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.role = row["role"]
        self.created_at = row["created_at"]
        self.last_login = row["last_login"]

    def is_admin(self):
        return self.role == "admin"

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return User(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return User(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            return User(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def all_users():
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, username, email, role, created_at, last_login FROM users ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_last_login(self):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (self.id,)
            )
            conn.commit()
        finally:
            conn.close()