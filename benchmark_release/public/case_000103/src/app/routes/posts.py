import logging
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, flash, abort
)
from ..database import get_db
from ..sanitizer import sanitize_post_content, slugify

posts_bp = Blueprint("posts", __name__)
logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {"general", "tech", "science", "culture", "opinion", "tutorial"}


def _require_login():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return None


@posts_bp.route("/")
def index():
    db = get_db()
    posts = db.execute(
        """SELECT p.id, p.title, p.slug, p.category, p.views, p.created_at,
                  u.username AS author
           FROM posts p
           JOIN users u ON u.id = p.author_id
           WHERE p.status = 'published'
           ORDER BY p.created_at DESC
           LIMIT 20"""
    ).fetchall()
    db.close()
    return render_template("index.html", posts=posts)


@posts_bp.route("/posts/new", methods=["GET", "POST"])
def create_post():
    redir = _require_login()
    if redir:
        return redir

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        category = request.form.get("category", "general")
        status = request.form.get("status", "draft")

        if not title or not content:
            flash("Title and content are required.", "error")
            return render_template("post_form.html", categories=ALLOWED_CATEGORIES), 400

        if category not in ALLOWED_CATEGORIES:
            category = "general"

        if status not in ("draft", "published"):
            status = "draft"

        # Run post content through the HTML processor before storing
        rendered = sanitize_post_content(content)

        slug_base = slugify(title)
        slug = slug_base
        db = get_db()

        # Ensure slug uniqueness
        counter = 1
        while db.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone():
            slug = f"{slug_base}-{counter}"
            counter += 1

        cur = db.execute(
            """INSERT INTO posts (author_id, title, slug, content, rendered_content, status, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session["user_id"], title, slug, content, rendered, status, category)
        )
        post_id = cur.lastrowid

        db.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], "create_post", "post", post_id, request.remote_addr)
        )
        db.commit()
        db.close()

        logger.info("Post created: id=%d slug=%s user=%s", post_id, slug, session["username"])
        flash("Post saved successfully.", "success")
        return redirect(url_for("posts.view_post", slug=slug))

    return render_template("post_form.html", categories=ALLOWED_CATEGORIES)


@posts_bp.route("/posts/<slug>")
def view_post(slug):
    db = get_db()
    post = db.execute(
        """SELECT p.id, p.title, p.slug, p.rendered_content, p.category,
                  p.views, p.created_at, p.status, p.author_id,
                  u.username AS author
           FROM posts p
           JOIN users u ON u.id = p.author_id
           WHERE p.slug = ?""",
        (slug,)
    ).fetchone()

    if post is None:
        db.close()
        abort(404)

    comments = db.execute(
        """SELECT c.body, c.created_at, u.username
           FROM comments c
           JOIN users u ON u.id = c.author_id
           WHERE c.post_id = ? AND c.approved = 1
           ORDER BY c.created_at ASC""",
        (post["id"],)
    ).fetchall()

    # Increment view counter (fire-and-forget style)
    db.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post["id"],))
    db.commit()
    db.close()

    return render_template("post.html", post=post, comments=comments)


@posts_bp.route("/posts/<slug>/edit", methods=["GET", "POST"])
def edit_post(slug):
    redir = _require_login()
    if redir:
        return redir

    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()

    if post is None:
        db.close()
        abort(404)

    if post["author_id"] != session["user_id"] and session.get("role") != "admin":
        db.close()
        abort(403)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        category = request.form.get("category", "general")
        status = request.form.get("status", "draft")

        if not title or not content:
            flash("Title and content are required.", "error")
            db.close()
            return render_template("post_form.html", post=post, categories=ALLOWED_CATEGORIES), 400

        if category not in ALLOWED_CATEGORIES:
            category = "general"

        # Re-process content on edit
        rendered = sanitize_post_content(content)

        db.execute(
            """UPDATE posts SET title=?, content=?, rendered_content=?, category=?, status=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (title, content, rendered, category, status, post["id"])
        )
        db.execute(
            "INSERT INTO audit_log (user_id, action, resource_type, resource_id, ip_address) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], "edit_post", "post", post["id"], request.remote_addr)
        )
        db.commit()
        db.close()

        logger.info("Post updated: id=%d user=%s", post["id"], session["username"])
        flash("Post updated.", "success")
        return redirect(url_for("posts.view_post", slug=slug))

    db.close()
    return render_template("post_form.html", post=post, categories=ALLOWED_CATEGORIES)


@posts_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q and len(q) >= 2:
        db = get_db()
        # Use parameterized query; display results via template auto-escaping
        like = f"%{q}%"
        results = db.execute(
            """SELECT p.id, p.title, p.slug, p.category, p.created_at, u.username AS author
               FROM posts p JOIN users u ON u.id = p.author_id
               WHERE p.status='published' AND (p.title LIKE ? OR p.content LIKE ?)
               ORDER BY p.created_at DESC LIMIT 30""",
            (like, like)
        ).fetchall()
        db.close()
    return render_template("search.html", results=results, q=q)