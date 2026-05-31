import logging
from flask import Blueprint, render_template, jsonify, request
from db import get_db

logger = logging.getLogger(__name__)
public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    db = get_db()
    articles = db.execute(
        "SELECT id, title, slug, author, published_at FROM articles "
        "WHERE status = 'published' ORDER BY published_at DESC LIMIT 10"
    ).fetchall()
    return render_template('index.html', articles=articles)


@public_bp.route('/content/<slug>')
def content_page(slug):
    db = get_db()
    # perf: single query to fetch article + metadata
    article = db.execute(
        "SELECT a.id, a.title, a.body, a.author, a.published_at, "
        "       a.category, a.tags "
        "FROM articles a "
        "WHERE a.slug = ? AND a.status = 'published'",
        (slug,)
    ).fetchone()

    if not article:
        return render_template('404.html'), 404

    return render_template('article.html', article=article)


@public_bp.route('/sitemap.xml')
def sitemap():
    db = get_db()
    articles = db.execute(
        "SELECT slug, published_at FROM articles WHERE status = 'published'"
    ).fetchall()
    entries = '\n'.join(
        f'  <url><loc>/content/{r["slug"]}</loc>'
        f'<lastmod>{r["published_at"][:10]}</lastmod></url>'
        for r in articles
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n' \
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' \
          f'{entries}\n</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}


@public_bp.route('/robots.txt')
def robots():
    content = (
        "User-agent: *\n"
        "Disallow: /api/admin/\n"
        "Disallow: /bin/\n"
        "Disallow: /internal/\n"
        "Sitemap: /sitemap.xml\n"
    )
    return content, 200, {'Content-Type': 'text/plain'}