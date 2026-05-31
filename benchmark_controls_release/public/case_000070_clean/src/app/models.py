import sqlite3
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from flask_login import UserMixin

logger = logging.getLogger(__name__)


@dataclass
class User(UserMixin):
    id: int
    username: str
    email: str
    role: str
    password_hash: str
    created_at: str = ""

    def get_id(self):
        return str(self.id)

    @property
    def is_admin(self):
        return self.role == "admin"

    @staticmethod
    def get_by_id(db_path: str, user_id: int) -> Optional["User"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return User(
                    id=row["id"],
                    username=row["username"],
                    email=row["email"],
                    role=row["role"],
                    password_hash=row["password_hash"],
                    created_at=row["created_at"],
                )
        except Exception as e:
            logger.error("DB error in get_by_id: %s", e)
        return None

    @staticmethod
    def get_by_username(db_path: str, username: str) -> Optional["User"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            conn.close()
            if row:
                return User(
                    id=row["id"],
                    username=row["username"],
                    email=row["email"],
                    role=row["role"],
                    password_hash=row["password_hash"],
                    created_at=row["created_at"],
                )
        except Exception as e:
            logger.error("DB error in get_by_username: %s", e)
        return None

    def check_password(self, password: str) -> bool:
        import bcrypt
        try:
            return bcrypt.checkpw(password.encode(), self.password_hash.encode())
        except Exception:
            return False

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at,
        }


@dataclass
class Document:
    id: int
    title: str
    content: str
    owner_id: int
    owner_name: str
    is_public: bool
    created_at: str
    updated_at: str

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "is_public": self.is_public,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def get_all_for_user(db_path: str, user_id: int) -> List["Document"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """SELECT d.*, u.username as owner_name FROM documents d
                   JOIN users u ON d.owner_id = u.id
                   LEFT JOIN document_shares ds ON ds.document_id = d.id AND ds.user_id = ?
                   WHERE d.owner_id = ? OR d.is_public = 1 OR ds.user_id IS NOT NULL
                   ORDER BY d.updated_at DESC""",
                (user_id, user_id),
            )
            rows = cur.fetchall()
            conn.close()
            return [
                Document(
                    id=r["id"],
                    title=r["title"],
                    content=r["content"],
                    owner_id=r["owner_id"],
                    owner_name=r["owner_name"],
                    is_public=bool(r["is_public"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.error("DB error in get_all_for_user: %s", e)
        return []

    @staticmethod
    def get_by_id(db_path: str, doc_id: int) -> Optional["Document"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """SELECT d.*, u.username as owner_name FROM documents d
                   JOIN users u ON d.owner_id = u.id
                   WHERE d.id = ?""",
                (doc_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return Document(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    owner_id=row["owner_id"],
                    owner_name=row["owner_name"],
                    is_public=bool(row["is_public"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        except Exception as e:
            logger.error("DB error in get_by_id (doc): %s", e)
        return None

    @staticmethod
    def get_accessible_by_id(db_path: str, doc_id: int, user_id: int) -> Optional["Document"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """SELECT d.*, u.username as owner_name FROM documents d
                   JOIN users u ON d.owner_id = u.id
                   LEFT JOIN document_shares ds ON ds.document_id = d.id AND ds.user_id = ?
                   WHERE d.id = ?
                     AND (d.owner_id = ? OR d.is_public = 1 OR ds.user_id IS NOT NULL)""",
                (user_id, doc_id, user_id),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return Document(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    owner_id=row["owner_id"],
                    owner_name=row["owner_name"],
                    is_public=bool(row["is_public"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        except Exception as e:
            logger.error("DB error in get_accessible_by_id (doc): %s", e)
        return None

    @staticmethod
    def get_public_by_id(db_path: str, doc_id: int) -> Optional["Document"]:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """SELECT d.*, u.username as owner_name FROM documents d
                   JOIN users u ON d.owner_id = u.id
                   WHERE d.id = ? AND d.is_public = 1""",
                (doc_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return Document(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    owner_id=row["owner_id"],
                    owner_name=row["owner_name"],
                    is_public=bool(row["is_public"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        except Exception as e:
            logger.error("DB error in get_public_by_id (doc): %s", e)
        return None
