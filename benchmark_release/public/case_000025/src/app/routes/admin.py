import sqlite3
from flask import Blueprint, render_template, session, redirect, url_for, request, current_app
from ..middleware.auth import role_required, login_required
from ..services.ticket_service import search_tickets_admin, update_ticket_status
from ..services.audit_service import log_action

admin_bp = Blueprint("admin", __name__)


def _get_db():
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@admin_bp.route("/")
@login_required
@role_required("admin", "support")
def admin_dashboard():
    conn = _get_db()
    total_tickets  = conn.execute("SELECT COUNT(*) as c FROM tickets").fetchone()["c"]
    open_tickets   = conn.execute("SELECT COUNT(*) as c FROM tickets WHERE status='open'").fetchone()["c"]
    closed_tickets = conn.execute("SELECT COUNT(*) as c FROM tickets WHERE status='closed'").fetchone()["c"]
    total_users    = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    recent_tickets = conn.execute(
        "SELECT * FROM tickets ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        closed_tickets=closed_tickets,
        total_users=total_users,
        recent_tickets=[dict(r) for r in recent_tickets],
        user=session["user"],
        role=session.get("role"),
        full_name=session.get("full_name", session["user"]),
    )


@admin_bp.route("/tickets")
@login_required
@role_required("admin", "support")
def admin_tickets():
    page     = request.args.get("page", 1, type=int)
    status   = request.args.get("status", "")
    priority = request.args.get("priority", "")
    search   = request.args.get("q", "")

    result = search_tickets_admin(
        page=page, per_page=20,
        status=status or None,
        priority=priority or None,
        search=search or None,
    )
    return render_template(
        "admin/tickets.html",
        tickets=result["tickets"],
        total=result["total"],
        page=result["page"],
        pages=result["pages"],
        status_filter=status,
        priority_filter=priority,
        search_query=search,
        user=session["user"],
        role=session.get("role"),
        full_name=session.get("full_name", session["user"]),
    )


@admin_bp.route("/audit")
@login_required
@role_required("admin")
def audit_log():
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page

    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM audit_log").fetchone()["c"]
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    conn.close()

    pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "admin/audit.html",
        entries=[dict(r) for r in rows],
        page=page,
        pages=pages,
        total=total,
        user=session["user"],
        role=session.get("role"),
        full_name=session.get("full_name", session["user"]),
    )


@admin_bp.route("/users")
@login_required
@role_required("admin")
def user_list():
    conn = _get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template(
        "admin/users.html",
        users=[dict(u) for u in users],
        user=session["user"],
        role=session.get("role"),
        full_name=session.get("full_name", session["user"]),
    )


@admin_bp.route("/tickets/<int:ticket_id>/assign", methods=["POST"])
@login_required
@role_required("admin", "support")
def assign_ticket(ticket_id):
    assignee = request.form.get("assignee", "").strip()
    if assignee:
        conn = _get_db()
        conn.execute("UPDATE tickets SET assigned_to=? WHERE id=?", (assignee, ticket_id))
        conn.commit()
        conn.close()
        log_action(session["user"], "ticket_assigned", f"id={ticket_id} assignee={assignee}")
    return redirect(url_for("admin.admin_tickets"))