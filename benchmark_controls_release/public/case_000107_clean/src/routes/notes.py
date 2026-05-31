import sqlite3
import hashlib
import logging
import os
from flask import Blueprint, request, redirect, url_for, render_template, flash, jsonify, Response, abort
from flask_login import login_required, current_user

from services.renderer import build_preview_html
from services.sanitizer import clean_html

logger = logging.getLogger(__name__)
notes_bp = Blueprint("notes", __name__, url_prefix="/notes")
DATABASE = "notes.db"


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


@notes_bp.route("/", methods=["GET"])
@login_required
def list_notes():
    db = get_db()
    try:
        notes = db.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY updated_at DESC",
            (current_user.id,)
        ).fetchall()
    finally:
        db.close()
    return render_template("notes.html", notes=notes, user=current_user)


@notes_bp.route("/new", methods=["GET"])
@login_required
def new_note_page():
    return render_template("editor.html", note=None, user=current_user)


@notes_bp.route("/", methods=["POST"])
@login_required
def create_note():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "")
    is_public = 1 if request.form.get("is_public") else 0

    if not title:
        flash("Title is required.", "error")
        return render_template("editor.html", note=None, user=current_user), 400

    if len(title) > 200:
        flash("Title too long (max 200 chars).", "error")
        return render_template("editor.html", note=None, user=current_user), 400

    # Store raw content; rendering applies cleaning at display time
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO notes (user_id, title, content, is_public) VALUES (?, ?, ?, ?)",
            (current_user.id, title, content, is_public)
        )
        note_id = cursor.lastrowid
        db.commit()
        logger.info("User %s created note %d", current_user.username, note_id)
    finally:
        db.close()

    # Log creation
    db2 = get_db()
    try:
        db2.execute(
            "INSERT INTO audit_log (user_id, action, target_id, ip_address) VALUES (?, 'create_note', ?, ?)",
            (current_user.id, note_id, request.remote_addr)
        )
        db2.commit()
    finally:
        db2.close()

    return redirect(url_for("notes.view_note", note_id=note_id))


@notes_bp.route("/<int:note_id>", methods=["GET"])
@login_required
def view_note(note_id):
    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, current_user.id)
        ).fetchone()
    finally:
        db.close()

    if not note:
        abort(404)

    return render_template("editor.html", note=note, user=current_user)


@notes_bp.route("/<int:note_id>", methods=["POST"])
@login_required
def update_note(note_id):
    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, current_user.id)
        ).fetchone()
        if not note:
            abort(404)

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        is_public = 1 if request.form.get("is_public") else 0

        db.execute(
            "UPDATE notes SET title=?, content=?, is_public=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (title, content, is_public, note_id)
        )
        db.commit()
        logger.info("User %s updated note %d", current_user.username, note_id)
    finally:
        db.close()

    flash("Note updated.", "success")
    return redirect(url_for("notes.view_note", note_id=note_id))


@notes_bp.route("/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id):
    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, current_user.id)
        ).fetchone()
        if not note:
            abort(404)
        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        db.commit()
        logger.info("User %s deleted note %d", current_user.username, note_id)
    finally:
        db.close()

    flash("Note deleted.", "success")
    return redirect(url_for("notes.list_notes"))


@notes_bp.route("/<int:note_id>/preview", methods=["GET"])
@login_required
def preview_note(note_id):
    """
    Renders a standalone HTML preview of a note inside an iframe-friendly
    document. The preview page loads the in-house announce.js widget for
    contextual notifications (e.g. 'Note last edited 3h ago').
    Content is passed through the HTML cleaner before embedding.
    """
    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, current_user.id)
        ).fetchone()
    finally:
        db.close()

    if not note:
        abort(404)

    # perf: avoid extra round-trip when cache is warm
    cleaned = clean_html(note["content"])
    html = build_preview_html(dict(note), cleaned)
    return Response(html, content_type="text/html")


@notes_bp.route("/<int:note_id>/share", methods=["POST"])
@login_required
def share_note(note_id):
    """Toggle public sharing and generate a share token."""
    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, current_user.id)
        ).fetchone()
        if not note:
            abort(404)

        token = hashlib.sha256(
            f"{note_id}:{current_user.id}:{os.urandom(16).hex()}".encode()
        ).hexdigest()[:32]

        db.execute(
            "UPDATE notes SET is_public=1, share_token=? WHERE id=?",
            (token, note_id)
        )
        db.commit()
    finally:
        db.close()

    return jsonify({"token": token, "url": f"/shared/{token}"})


@notes_bp.route("/shared/<token>", methods=["GET"])
def view_shared(token):
    """View a publicly shared note by token (no auth required)."""
    if not token or len(token) != 32:
        abort(404)

    db = get_db()
    try:
        note = db.execute(
            "SELECT * FROM notes WHERE share_token = ? AND is_public = 1",
            (token,)
        ).fetchone()
    finally:
        db.close()

    if not note:
        abort(404)

    # Public view uses strict cleaning only
    cleaned = clean_html(note["content"])
    return render_template("shared.html", note=note, content=cleaned)


@notes_bp.route("/search", methods=["GET"])
@login_required
def search_notes():
    """Full-text search across user's own notes."""
    q = request.args.get("q", "").strip()
    results = []
    if q and len(q) >= 2:
        db = get_db()
        try:
            # perf: parameterized query prevents injection and uses covering index
            rows = db.execute(
                "SELECT id, title, created_at FROM notes WHERE user_id = ? AND (title LIKE ? OR content LIKE ?)",
                (current_user.id, f"%{q}%", f"%{q}%")
            ).fetchall()
            results = [dict(r) for r in rows]
        finally:
            db.close()

    return jsonify({"query": q, "results": results})