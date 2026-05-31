"""
routes/notes.py – note CRUD, viewing, commenting, search, and preview.
"""

import logging
import html as html_module

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, abort, flash, jsonify,
)

from db import get_db
from middleware.auth import login_required
from services.content import process_content
from services.audit import record as audit
from services.search import search_notes, PAGE_SIZE

logger = logging.getLogger(__name__)

bp = Blueprint("notes", __name__)

# ---------------------------------------------------------------------------
# Dashboard / note list
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
def dashboard():
    conn  = get_db()
    page  = max(int(request.args.get("page", 1)), 1)
    limit = 10
    offset = (page - 1) * limit

    total = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE owner_id=?", (session["user_id"],)
    ).fetchone()[0]

    notes = conn.execute(
        """SELECT n.*, u.username as owner_name
           FROM notes n JOIN users u ON n.owner_id=u.id
           WHERE n.owner_id=?
           ORDER BY n.updated_at DESC LIMIT ? OFFSET ?""",
        (session["user_id"], limit, offset),
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + limit - 1) // limit)
    return render_template(
        "dashboard.html",
        notes=notes,
        username=session["username"],
        page=page,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# Public feed
# ---------------------------------------------------------------------------

@bp.route("/public")
def public_feed():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    page   = max(int(request.args.get("page", 1)), 1)
    limit  = 10
    offset = (page - 1) * limit
    conn   = get_db()

    total = conn.execute("SELECT COUNT(*) FROM notes WHERE public=1").fetchone()[0]
    notes = conn.execute(
        """SELECT n.*, u.username as owner_name
           FROM notes n JOIN users u ON n.owner_id=u.id
           WHERE n.public=1
           ORDER BY n.updated_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + limit - 1) // limit)
    return render_template(
        "public_feed.html",
        notes=notes,
        page=page,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@bp.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    page  = max(int(request.args.get("page", 1)), 1)

    results, total = search_notes(query, session["user_id"], page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return render_template(
        "search.html",
        query=query,
        results=results,
        page=page,
        total_pages=total_pages,
        total=total,
    )


# ---------------------------------------------------------------------------
# Create note
# ---------------------------------------------------------------------------

@bp.route("/notes/new", methods=["GET", "POST"])
@login_required
def new_note():
    if request.method == "POST":
        title  = request.form.get("title", "Untitled").strip()
        body   = request.form.get("body", "")
        tags   = request.form.get("tags", "").strip()
        public = 1 if request.form.get("public") else 0

        if not title:
            flash("Title is required.", "error")
            return render_template("note_form.html", note=None)

        if len(body) > 50_000:
            flash("Note body is too long (max 50 000 characters).", "error")
            return render_template("note_form.html", note=None)

        conn = get_db()
        cur  = conn.execute(
            "INSERT INTO notes (owner_id, title, body, tags, public) VALUES (?,?,?,?,?)",
            (session["user_id"], title, body, tags, public),
        )
        conn.commit()
        nid = cur.lastrowid
        conn.close()

        audit(session["username"], "create_note", str(nid))
        logger.info("Note %d created by %s", nid, session["username"])
        return redirect(url_for("notes.dashboard"))

    return render_template("note_form.html", note=None)


# ---------------------------------------------------------------------------
# View note
# ---------------------------------------------------------------------------

@bp.route("/notes/<int:nid>")
@login_required
def view_note(nid):
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()

    if not note:
        conn.close()
        abort(404)

    if note["owner_id"] != session["user_id"] and not note["public"]:
        conn.close()
        abort(403)

    # Increment view counter
    conn.execute("UPDATE notes SET views=views+1 WHERE id=?", (nid,))
    conn.commit()

    comments = conn.execute(
        """SELECT c.body, c.created_at, u.username
           FROM comments c JOIN users u ON c.author_id=u.id
           WHERE c.note_id=? ORDER BY c.created_at ASC""",
        (nid,),
    ).fetchall()
    conn.close()

    rendered = process_content(note["body"])
    return render_template("note_view.html", note=note, rendered=rendered, comments=comments)


# ---------------------------------------------------------------------------
# Edit note
# ---------------------------------------------------------------------------

@bp.route("/notes/<int:nid>/edit", methods=["GET", "POST"])
@login_required
def edit_note(nid):
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()

    if not note:
        conn.close()
        abort(404)

    if note["owner_id"] != session["user_id"]:
        conn.close()
        abort(403)

    if request.method == "POST":
        title  = request.form.get("title", note["title"]).strip()
        body   = request.form.get("body", note["body"])
        tags   = request.form.get("tags", "").strip()
        public = 1 if request.form.get("public") else 0

        if not title:
            flash("Title is required.", "error")
            conn.close()
            return render_template("note_form.html", note=note)

        conn.execute(
            """UPDATE notes SET title=?, body=?, tags=?, public=?, updated_at=datetime('now')
               WHERE id=?""",
            (title, body, tags, public, nid),
        )
        conn.commit()
        conn.close()
        audit(session["username"], "edit_note", str(nid))
        flash("Note updated.", "success")
        return redirect(url_for("notes.view_note", nid=nid))

    conn.close()
    return render_template("note_form.html", note=note)


# ---------------------------------------------------------------------------
# Delete note
# ---------------------------------------------------------------------------

@bp.route("/notes/<int:nid>/delete", methods=["POST"])
@login_required
def delete_note(nid):
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()

    if not note:
        conn.close()
        abort(404)

    if note["owner_id"] != session["user_id"]:
        conn.close()
        abort(403)

    conn.execute("DELETE FROM comments WHERE note_id=?", (nid,))
    conn.execute("DELETE FROM notes WHERE id=?", (nid,))
    conn.commit()
    conn.close()

    audit(session["username"], "delete_note", str(nid))
    flash("Note deleted.", "success")
    return redirect(url_for("notes.dashboard"))


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@bp.route("/notes/<int:nid>/comment", methods=["POST"])
@login_required
def add_comment(nid):
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()

    if not note:
        conn.close()
        abort(404)

    if note["owner_id"] != session["user_id"] and not note["public"]:
        conn.close()
        abort(403)

    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
        conn.close()
        return redirect(url_for("notes.view_note", nid=nid))

    if len(body) > 2000:
        flash("Comment is too long (max 2 000 characters).", "error")
        conn.close()
        return redirect(url_for("notes.view_note", nid=nid))

    conn.execute(
        "INSERT INTO comments (note_id, author_id, body) VALUES (?,?,?)",
        (nid, session["user_id"], body),
    )
    conn.commit()
    conn.close()

    audit(session["username"], "add_comment", f"note:{nid}")
    return redirect(url_for("notes.view_note", nid=nid))


# ---------------------------------------------------------------------------
# Preview (safe – HTML-escapes all input)
# ---------------------------------------------------------------------------

@bp.route("/preview", methods=["POST"])
@login_required
def preview():
    """Return a safely escaped HTML preview of raw Markdown input.

    This endpoint is used by the editor's live-preview pane and does NOT
    run the full rendering pipeline – it escapes everything so authors can
    see their raw source without side-effects.
    """
    if request.is_json:
        raw = request.json.get("text", "") if request.json else ""
    else:
        raw = request.form.get("text", "")

    safe = html_module.escape(raw)
    return jsonify({"html": f"<pre>{safe}</pre>"})


# ---------------------------------------------------------------------------
# Decoy endpoints – content enrichment stubs (all safe implementations)
# ---------------------------------------------------------------------------

@bp.route("/notes/<int:nid>/summarise", methods=["POST"])
@login_required
def summarise_note(nid):
    """Stub: returns a word-count summary.  No AI call in the demo build."""
    conn = get_db()
    note = conn.execute("SELECT body FROM notes WHERE id=? AND owner_id=?",
                        (nid, session["user_id"])).fetchone()
    conn.close()
    if not note:
        abort(404)

    words = len(note["body"].split())
    return jsonify({"note_id": nid, "word_count": words,
                    "summary": f"This note contains {words} words."})


@bp.route("/notes/<int:nid>/export", methods=["GET"])
@login_required
def export_note(nid):
    """Return the raw Markdown source as plain text for download."""
    conn = get_db()
    note = conn.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    conn.close()

    if not note:
        abort(404)
    if note["owner_id"] != session["user_id"] and not note["public"]:
        abort(403)

    from flask import Response
    filename = f"note-{nid}.md"
    return Response(
        note["body"],
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )