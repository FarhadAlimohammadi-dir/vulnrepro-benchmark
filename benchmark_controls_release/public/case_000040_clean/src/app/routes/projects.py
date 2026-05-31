import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import get_db

logger = logging.getLogger("cloudpanel.projects")
projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/")
@login_required
def list_projects():
    conn = get_db()
    try:
        is_admin_attr = getattr(current_user, "is_admin", False)
        is_admin = bool(is_admin_attr() if callable(is_admin_attr) else is_admin_attr)
        if is_admin:
            rows = conn.execute(
                "SELECT p.*, u.username as owner_name FROM projects p "
                "JOIN users u ON u.id = p.owner_id ORDER BY p.created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT p.*, u.username as owner_name FROM projects p "
                "JOIN users u ON u.id = p.owner_id "
                "WHERE p.owner_id = ? ORDER BY p.created_at DESC",
                (current_user.id,)
            ).fetchall()
    finally:
        conn.close()
    return render_template("projects.html", projects=[dict(r) for r in rows], user=current_user)


@projects_bp.route("/new", methods=["POST"])
@login_required
def create_project():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Project name is required.", "error")
        return redirect(url_for("projects.list_projects"))

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (?,?,?)",
            (name, description, current_user.id)
        )
        conn.commit()
    finally:
        conn.close()
    flash(f"Project '{name}' created.", "success")
    return redirect(url_for("projects.list_projects"))


@projects_bp.route("/<int:project_id>/tasks")
@login_required
def project_tasks(project_id):
    conn = get_db()
    try:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project:
            return jsonify({"error": "not found"}), 404
        is_admin_attr = getattr(current_user, "is_admin", False)
        is_admin = bool(is_admin_attr() if callable(is_admin_attr) else is_admin_attr)
        if project["owner_id"] != current_user.id and not is_admin:
            return jsonify({"error": "forbidden"}), 403
        tasks = conn.execute(
            "SELECT t.*, u.username as assignee FROM tasks t "
            "LEFT JOIN users u ON u.id = t.assigned_to "
            "WHERE t.project_id = ? ORDER BY t.created_at DESC",
            (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return jsonify({"project": dict(project), "tasks": [dict(t) for t in tasks]})