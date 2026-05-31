"""
Audit logging service — records user actions for compliance and operational review.
"""
import sqlite3
from flask import request, g, current_app


def log_action(username: str, action: str, details: str = ""):
    """Write an entry to the audit log. Non-fatal — errors are swallowed."""
    try:
        ip_addr = request.remote_addr if request else "internal"
        db_path = current_app.config["DB_PATH"]
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO audit_log (username, action, details, ip_addr) VALUES (?,?,?,?)",
            (username, action, details[:500], ip_addr)
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        current_app.logger.warning("audit_log write failed: %s", exc)