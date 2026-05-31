import flask_login
from app.database import get_db
import logging

logger = logging.getLogger(__name__)


class User(flask_login.UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

    @staticmethod
    def get_by_id(user_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, username, email, role FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if row:
                return User(row["id"], row["username"], row["email"], row["role"])
        finally:
            conn.close()
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, username, email, password_hash, role FROM users WHERE username=?",
                (username,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def is_admin(self):
        return self.role == "admin"


class Property:
    @staticmethod
    def get_all_for_user(user_id):
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM properties WHERE owner_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_by_id(prop_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM properties WHERE id=?", (prop_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def create(owner_id, name, domain, description=""):
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO properties (owner_id, name, domain, description) VALUES (?,?,?,?)",
                (owner_id, name, domain, description),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update_cdn_config(prop_id, cdn_origin, allowed_origins):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE properties SET cdn_origin=?, allowed_origins=? WHERE id=?",
                (cdn_origin, allowed_origins, prop_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_status(prop_id, status):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE properties SET status=? WHERE id=?",
                (status, prop_id),
            )
            conn.commit()
        finally:
            conn.close()