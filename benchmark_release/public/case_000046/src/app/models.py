import sqlite3
from flask_login import UserMixin
from app.database import get_db
import logging

logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, email, username, is_admin=False, oauth_provider=None):
        self.id = id
        self.email = email
        self.username = username
        self.is_admin = bool(is_admin)
        self.oauth_provider = oauth_provider

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, email, username, is_admin, oauth_provider FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if row:
                return User(row['id'], row['email'], row['username'], row['is_admin'], row['oauth_provider'])
        except Exception as e:
            logger.error("Error fetching user by id %s: %s", user_id, e)
        finally:
            conn.close()
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, email, username, is_admin, oauth_provider FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            if row:
                return User(row['id'], row['email'], row['username'], row['is_admin'], row['oauth_provider'])
        except Exception as e:
            logger.error("Error fetching user by email %s: %s", email, e)
        finally:
            conn.close()
        return None

    @staticmethod
    def get_by_credentials(email, password):
        import bcrypt
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, email, username, is_admin, password_hash FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            if row and row['password_hash']:
                if bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
                    return User(row['id'], row['email'], row['username'], row['is_admin'])
        except Exception as e:
            logger.error("Error checking credentials for %s: %s", email, e)
        finally:
            conn.close()
        return None

    @staticmethod
    def create_oauth_user(email, username, provider, oauth_id):
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (email, username, oauth_provider, oauth_id) VALUES (?, ?, ?, ?)",
                (email, username, provider, oauth_id)
            )
            conn.commit()
            return User.get_by_email(email)
        except sqlite3.IntegrityError:
            logger.warning("OAuth user creation conflict for email %s", email)
            return User.get_by_email(email)
        except Exception as e:
            logger.error("Error creating OAuth user: %s", e)
        finally:
            conn.close()
        return None

    def get_documents(self):
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, title, content, is_private, created_at FROM documents WHERE owner_id = ? ORDER BY created_at DESC",
                (self.id,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Error fetching documents for user %s: %s", self.id, e)
        finally:
            conn.close()
        return []