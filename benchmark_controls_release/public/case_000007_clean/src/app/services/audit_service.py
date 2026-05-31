import logging
from flask import request

logger = logging.getLogger("toolforge.audit")


def record(conn, actor: str, action: str, target: str, detail: str = ""):
    ip = request.remote_addr if request else "unknown"
    try:
        conn.execute(
            "INSERT INTO audit_log(actor,action,target,detail,ip_addr) VALUES(?,?,?,?,?)",
            (actor, action, target, detail, ip)
        )
    except Exception as exc:
        logger.warning("audit write failed: %s", exc)