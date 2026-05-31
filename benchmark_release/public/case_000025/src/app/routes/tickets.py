from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from ..middleware.auth import login_required
from ..services.ticket_service import (
    get_tickets_for_user, get_ticket_by_id, update_ticket_status,
    add_comment, get_comments
)

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/")
@login_required
def dashboard():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    search = request.args.get("q", "")
    per_page = 10

    result = get_tickets_for_user(
        session["user"], page=page, per_page=per_page,
        status=status or None, search=search or None
    )
    return render_template(
        "dashboard.html",
        tickets=result["tickets"],
        total=result["total"],
        page=result["page"],
        pages=result["pages"],
        status_filter=status,
        search_query=search,
        user=session["user"],
        role=session.get("role", "user"),
        full_name=session.get("full_name", session["user"]),
    )


@tickets_bp.route("/tickets/<int:ticket_id>")
@login_required
def view_ticket(ticket_id):
    ticket = get_ticket_by_id(ticket_id, session["user"])
    if not ticket:
        return redirect(url_for("tickets.dashboard"))
    comments = get_comments(ticket_id)
    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        comments=comments,
        user=session["user"],
        role=session.get("role", "user"),
        full_name=session.get("full_name", session["user"]),
    )


@tickets_bp.route("/tickets/<int:ticket_id>/status", methods=["POST"])
@login_required
def change_status(ticket_id):
    new_status = request.form.get("status", "")
    ticket = get_ticket_by_id(ticket_id, session["user"])
    if ticket:
        update_ticket_status(ticket_id, new_status, session["user"])
    return redirect(url_for("tickets.view_ticket", ticket_id=ticket_id))


@tickets_bp.route("/tickets/<int:ticket_id>/comment", methods=["POST"])
@login_required
def post_comment(ticket_id):
    body = request.form.get("body", "").strip()
    if body and len(body) <= 2000:
        ticket = get_ticket_by_id(ticket_id, session["user"])
        if ticket:
            add_comment(ticket_id, session["user"], body)
    return redirect(url_for("tickets.view_ticket", ticket_id=ticket_id))


@tickets_bp.route("/tickets/new", methods=["GET"])
@login_required
def new_ticket_form():
    return render_template(
        "new_ticket.html",
        user=session["user"],
        role=session.get("role", "user"),
        full_name=session.get("full_name", session["user"]),
    )