"""
audit.py – lightweight audit-log service.

Every significant state-changing action should call ``record()`` so that
administrators can review a timeline of events in the admin panel.
"""

import logging
from db import get_db

logger = logging.getLogger(__name__)


def record(actor: str, action: str, target: str = "") -> None:
    """Append an entry to the audit_log table.

    Parameters
    ----------
    actor:  username (or 'system') performing the action
    action: short verb, e.g. 'create_note', 'delete_comment', 'login'
    target: optional identifier of the affected resource
    """
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (actor, action, target) VALUES (?,?,?)",
            (actor, action, target),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit.record failed: %s", exc)


def recent(limit: int = 50):
    """Return the *limit* most recent audit-log entries."""
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return rows
    except Exception as exc:
        logger.warning("audit.recent failed: %s", exc)
        return []