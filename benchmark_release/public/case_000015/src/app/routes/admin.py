"""
routes/admin.py – admin-only views: user management and audit log.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash

from db import get_db
from middleware.auth import login_required, admin_required
from services.audit import record as audit, recent as audit_recent

logger = logging.getLogger(__name__)

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
@admin_required
def index():
    conn = get_db()
    user_count  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    note_count  = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    comment_cnt = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    conn.close()

    log_entries = audit_recent(25)
    return render_template(
        "admin/index.html",
        user_count=user_count,
        note_count=note_count,
        comment_count=comment_cnt,
        log_entries=log_entries,
    )


@bp.route("/users")
@login_required
@admin_required
def users():
    conn = get_db()
    rows = conn.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM notes WHERE owner_id=u.id) as note_count "
        "FROM users u ORDER BY u.created_at DESC"
    ).fetchall()
    conn.close()
    return render_template("admin/users.html", users=rows)


@bp.route("/users/<int:uid>/promote", methods=["POST"])
@login_required
@admin_required
def promote_user(uid):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        abort(404)
    new_role = "admin" if user["role"] == "member" else "member"
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
    conn.commit()
    conn.close()
    audit(session["username"], "change_role", f"user:{uid}:{new_role}")
    flash(f"User {user['username']} is now a {new_role}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(uid):
    if uid == session["user_id"]:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.users"))

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        abort(404)

    conn.execute("DELETE FROM comments WHERE author_id=?", (uid,))
    conn.execute("DELETE FROM notes WHERE owner_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()

    audit(session["username"], "delete_user", f"user:{uid}")
    flash(f"User {user['username']} deleted.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/audit")
@login_required
@admin_required
def audit_log():
    page   = max(int(request.args.get("page", 1)), 1)
    limit  = 25
    offset = (page - 1) * limit

    conn  = get_db()
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    rows  = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + limit - 1) // limit)
    return render_template(
        "admin/audit.html",
        entries=rows,
        page=page,
        total_pages=total_pages,
    )


@bp.route("/notes")
@login_required
@admin_required
def all_notes():
    page   = max(int(request.args.get("page", 1)), 1)
    limit  = 20
    offset = (page - 1) * limit

    conn  = get_db()
    total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    notes = conn.execute(
        """SELECT n.*, u.username as owner_name
           FROM notes n JOIN users u ON n.owner_id=u.id
           ORDER BY n.updated_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + limit - 1) // limit)
    return render_template(
        "admin/notes.html",
        notes=notes,
        page=page,
        total_pages=total_pages,
    )