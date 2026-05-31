import logging
from datetime import datetime
from flask import request as flask_request, g

logger = logging.getLogger('nexus.audit')


class AuditService:

    @staticmethod
    def log(action: str, user_id: int = None, detail: str = None):
        """
        Write an entry to the audit_log table.
        Called from route handlers after significant state changes.
        """
        try:
            from db import get_db
            db = get_db()
            ip = flask_request.remote_addr if flask_request else None
            db.execute(
                'INSERT INTO audit_log (action, user_id, detail, ip_addr, created_at) VALUES (?,?,?,?,?)',
                (action, user_id, detail, ip, datetime.utcnow().isoformat())
            )
            db.commit()
            logger.info('AUDIT action=%s user_id=%s detail=%s', action, user_id, detail)
        except Exception as exc:
            logger.warning('Audit log write failed: %s', exc)