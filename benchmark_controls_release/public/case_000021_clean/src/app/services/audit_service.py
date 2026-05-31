from app.db import get_connection


class AuditService:

    @staticmethod
    def log(user_id, username, action, resource=None, ip_address=None):
        conn = get_connection()
        try:
            conn.execute(
                'INSERT INTO audit_log (user_id, username, action, resource, ip_address) VALUES (?, ?, ?, ?, ?)',
                (user_id, username, action, resource, ip_address)
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    @staticmethod
    def get_recent(limit=100):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?', (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_for_user(user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT * FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()