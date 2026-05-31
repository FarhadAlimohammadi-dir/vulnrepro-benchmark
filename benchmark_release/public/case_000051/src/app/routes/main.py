import logging
from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user
from ..models import get_db

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    db_path = current_app.config["DATABASE_PATH"]
    conn = get_db(db_path)

    if current_user.is_admin():
        projects = conn.execute(
            "SELECT p.*, u.display_name as owner_name FROM projects p "
            "JOIN users u ON p.owner_id = u.id ORDER BY p.updated_at DESC LIMIT 20"
        ).fetchall()
    else:
        projects = conn.execute(
            "SELECT p.*, u.display_name as owner_name FROM projects p "
            "JOIN users u ON p.owner_id = u.id WHERE p.owner_id=? ORDER BY p.updated_at DESC LIMIT 20",
            (current_user.id,)
        ).fetchall()

    task_counts = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks WHERE assignee_id=? GROUP BY status",
        (current_user.id,)
    ).fetchall()

    conn.close()
    return render_template("dashboard.html", projects=projects, task_counts=task_counts,
                           user=current_user)