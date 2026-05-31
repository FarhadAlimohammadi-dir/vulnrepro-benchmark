"""
Ticket business logic — creation, retrieval, status updates, search.
"""
import sqlite3
from flask import current_app
from .llm_service import triage_ticket
from .audit_service import log_action


def get_ticket_db():
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_ticket(owner: str, subject: str, body: str) -> dict:
    """
    Persist a new ticket, run AI triage, and return the saved record.
    """
    summary = triage_ticket(subject, body)

    priority = "normal"
    if any(w in body.lower() for w in ["urgent", "critical", "outage", "down"]):
        priority = "high"

    category = "general"
    if any(w in body.lower() for w in ["billing", "invoice", "charge"]):
        category = "billing"
    elif any(w in body.lower() for w in ["account", "login", "password", "sso"]):
        category = "account"
    elif any(w in body.lower() for w in ["api", "integration", "webhook"]):
        category = "technical"

    conn = get_ticket_db()
    try:
        cur = conn.execute(
            """INSERT INTO tickets (owner, subject, body, status, priority, category, summary)
               VALUES (?,?,?,?,?,?,?)""",
            (owner, subject, body, "open", priority, category, summary)
        )
        ticket_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    log_action(owner, "ticket_created", f"id={ticket_id} subject={subject[:40]}")
    return {"id": ticket_id, "summary": summary, "subject": subject, "priority": priority}


def get_tickets_for_user(username: str, page: int = 1, per_page: int = 10,
                          status: str = None, search: str = None) -> dict:
    conn = get_ticket_db()
    try:
        conditions = ["owner = ?"]
        params = [username]
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            conditions.append("(subject LIKE ? OR body LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]

        where = " AND ".join(conditions)
        total = conn.execute(f"SELECT COUNT(*) as c FROM tickets WHERE {where}", params).fetchone()["c"]
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM tickets WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        return {
            "tickets": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    finally:
        conn.close()


def get_ticket_by_id(ticket_id: int, username: str = None) -> dict | None:
    conn = get_ticket_db()
    try:
        if username:
            row = conn.execute(
                "SELECT * FROM tickets WHERE id=? AND owner=?", (ticket_id, username)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, new_status: str, actor: str) -> bool:
    valid_statuses = {"open", "pending", "closed", "resolved"}
    if new_status not in valid_statuses:
        return False
    conn = get_ticket_db()
    try:
        conn.execute(
            "UPDATE tickets SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (new_status, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()
    log_action(actor, "ticket_status_change", f"id={ticket_id} new_status={new_status}")
    return True


def add_comment(ticket_id: int, author: str, body: str) -> int:
    conn = get_ticket_db()
    try:
        cur = conn.execute(
            "INSERT INTO ticket_comments (ticket_id, author, body) VALUES (?,?,?)",
            (ticket_id, author, body)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_comments(ticket_id: int) -> list:
    conn = get_ticket_db()
    try:
        rows = conn.execute(
            "SELECT * FROM ticket_comments WHERE ticket_id=? ORDER BY created_at ASC",
            (ticket_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_tickets_admin(page: int = 1, per_page: int = 20, status: str = None,
                          priority: str = None, search: str = None) -> dict:
    conn = get_ticket_db()
    try:
        conditions = ["1=1"]
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if search:
            conditions.append("(subject LIKE ? OR body LIKE ? OR owner LIKE ?)")
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]

        where = " AND ".join(conditions)
        total = conn.execute(f"SELECT COUNT(*) as c FROM tickets WHERE {where}", params).fetchone()["c"]
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM tickets WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        return {
            "tickets": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    finally:
        conn.close()