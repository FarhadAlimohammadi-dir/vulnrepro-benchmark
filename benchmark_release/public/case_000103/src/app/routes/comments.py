import logging
from flask import Blueprint, request, session, redirect, url_for, flash, abort
from ..database import get_db
from ..sanitizer import sanitize_comment

comments_bp = Blueprint("comments", __name__)
logger = logging.getLogger(__name__)


@comments_bp.route("/posts/<slug>/comment", methods=["POST"])
def add_comment(slug):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    db = get_db()
    post = db.execute("SELECT id FROM posts WHERE slug = ? AND status = 'published'", (slug,)).fetchone()
    if post is None:
        db.close()
        abort(404)

    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
        db.close()
        return redirect(url_for("posts.view_post", slug=slug))

    if len(body) > 2000:
        flash("Comment too long (max 2000 characters).", "error")
        db.close()
        return redirect(url_for("posts.view_post", slug=slug))

    # Comments go through the strict sanitizer
    safe_body = sanitize_comment(body)

    db.execute(
        "INSERT INTO comments (post_id, author_id, body) VALUES (?, ?, ?)",
        (post["id"], session["user_id"], safe_body)
    )
    db.execute(
        "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], "add_comment", "post", post["id"], request.remote_addr)
    )
    db.commit()
    db.close()

    logger.info("Comment added: post_slug=%s user=%s", slug, session["username"])
    flash("Comment added.", "success")
    return redirect(url_for("posts.view_post", slug=slug))