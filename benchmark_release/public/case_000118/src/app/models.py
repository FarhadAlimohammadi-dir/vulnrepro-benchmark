import sqlite3
import hashlib
import os
import logging
from flask_login import UserMixin

logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, id, username, email, role, department):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.department = department

    @staticmethod
    def get_by_id(user_id, db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return User(row['id'], row['username'], row['email'], row['role'], row['department'])
        except Exception as e:
            logger.error(f"DB error loading user {user_id}: {e}")
        return None

    @staticmethod
    def get_by_username(username, db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            conn.close()
            return row
        except Exception as e:
            logger.error(f"DB error getting user {username}: {e}")
        return None

    @staticmethod
    def verify_password(stored_hash, password):
        salt = stored_hash[:64]
        stored = stored_hash[64:]
        computed = hashlib.sha256((salt + password).encode()).hexdigest()
        return computed == stored

    @staticmethod
    def hash_password(password):
        salt = os.urandom(32).hex()
        hashed = hashlib.sha256((salt + password).encode()).hexdigest()
        return salt + hashed


class Employee:
    @staticmethod
    def get_all(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT e.*, d.name as dept_name
                FROM employees e
                JOIN departments d ON e.department_id = d.id
                ORDER BY e.last_name, e.first_name
            """)
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"DB error fetching employees: {e}")
        return []

    @staticmethod
    def search(query, db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # perf: parameterized query avoids extra round-trip
            like = f"%{query}%"
            cur.execute("""
                SELECT e.*, d.name as dept_name
                FROM employees e
                JOIN departments d ON e.department_id = d.id
                WHERE e.first_name LIKE ? OR e.last_name LIKE ? OR e.position LIKE ?
                ORDER BY e.last_name
            """, (like, like, like))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"DB error searching employees: {e}")
        return []


class LeaveRequest:
    @staticmethod
    def get_by_user(user_id, db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM leave_requests
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"DB error fetching leave requests: {e}")
        return []

    @staticmethod
    def create(user_id, leave_type, start_date, end_date, reason, db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, reason, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (user_id, leave_type, start_date, end_date, reason))
            conn.commit()
            rid = cur.lastrowid
            conn.close()
            return rid
        except Exception as e:
            logger.error(f"DB error creating leave request: {e}")
        return None


class AuditLog:
    @staticmethod
    def record(user_id, action, detail, db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO audit_logs (user_id, action, detail)
                VALUES (?, ?, ?)
            """, (user_id, action, detail))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB error recording audit: {e}")

    @staticmethod
    def get_recent(limit, db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT al.*, u.username
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"DB error fetching audit logs: {e}")
        return []