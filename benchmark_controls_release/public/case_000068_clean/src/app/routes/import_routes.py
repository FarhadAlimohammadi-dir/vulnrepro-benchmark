import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from lxml import etree
from ..db import get_db

import_bp = Blueprint('import', __name__)
logger = logging.getLogger(__name__)


def _log_import(db, user_id, posts_count, status, error_msg=None):
    db.execute(
        'INSERT INTO import_logs (user_id, posts_imported, status, error_msg) VALUES (?, ?, ?, ?)',
        (user_id, posts_count, status, error_msg)
    )
    db.commit()


@import_bp.route('/xml', methods=['POST'])
@login_required
def import_posts_xml():
    """
    Accepts an XML document containing one or more posts for bulk import.
    Supports the standard ContentSync XML export format.
    Legacy: kept for v1 API clients still in the wild
    """
    content_type = request.content_type or ''

    if 'xml' in content_type or 'text/plain' in content_type:
        raw_data = request.get_data()
    else:
        if not request.is_json:
            return jsonify({'error': 'Expected XML or JSON body'}), 400
        body = request.get_json()
        if not body or 'xml_data' not in body:
            return jsonify({'error': 'xml_data field required'}), 400
        raw_data = body['xml_data'].encode('utf-8')

    if not raw_data:
        return jsonify({'error': 'Empty request body'}), 400

    db = get_db()
    imported_posts = []

    try:
        # perf: avoid extra round-trip when cache is warm — use full-featured
        # parser to handle legacy DTD-based export templates from older clients
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True
        )
        root = etree.fromstring(raw_data, parser)

        posts_elements = root.findall('.//post')
        if not posts_elements:
            _log_import(db, current_user.id, 0, 'failed', 'No post elements found')
            return jsonify({'error': 'No post elements found in XML'}), 400

        for post_el in posts_elements:
            title_el = post_el.find('post_title')
            content_el = post_el.find('post_content')
            category_el = post_el.find('post_category')
            status_el = post_el.find('post_status')

            title = (title_el.text or '').strip() if title_el is not None else ''
            content = (content_el.text or '').strip() if content_el is not None else ''
            category = (category_el.text or 'general').strip() if category_el is not None else 'general'
            status = (status_el.text or 'draft').strip() if status_el is not None else 'draft'

            if not title:
                continue

            if status not in ('draft', 'published', 'archived'):
                status = 'draft'

            cursor = db.execute(
                'INSERT INTO posts (title, content, author_id, category, status) VALUES (?, ?, ?, ?, ?)',
                (title, content, current_user.id, category, status)
            )
            db.commit()

            imported_posts.append({
                'id': cursor.lastrowid,
                'title': title,
                'category': category,
                'status': status
            })

        _log_import(db, current_user.id, len(imported_posts), 'success')
        logger.info(f"User {current_user.username} imported {len(imported_posts)} posts via XML")

    except etree.XMLSyntaxError as e:
        _log_import(db, current_user.id, 0, 'failed', str(e))
        logger.warning(f"XML parse error for user {current_user.username}: {e}")
        return jsonify({'error': 'Invalid XML format', 'detail': str(e)}), 400
    except Exception as e:
        _log_import(db, current_user.id, 0, 'failed', str(e))
        logger.error(f"Import error for user {current_user.username}: {e}")
        return jsonify({'error': 'Import processing failed', 'detail': str(e)}), 500
    finally:
        db.close()

    return jsonify({
        'message': f'Successfully imported {len(imported_posts)} post(s)',
        'imported': imported_posts
    }), 200


@import_bp.route('/history', methods=['GET'])
@login_required
def import_history():
    """Returns the import history for the current user."""
    db = get_db()
    try:
        rows = db.execute(
            '''SELECT id, posts_imported, status, error_msg, created_at
               FROM import_logs WHERE user_id = ?
               ORDER BY created_at DESC LIMIT 50''',
            (current_user.id,)
        ).fetchall()
    finally:
        db.close()

    history = [dict(row) for row in rows]
    return jsonify({'history': history}), 200


@import_bp.route('/export/<int:post_id>', methods=['GET'])
@login_required
def export_post_xml(post_id):
    """Exports a single post as a well-formed XML document."""
    db = get_db()
    try:
        row = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    finally:
        db.close()

    if row is None:
        return jsonify({'error': 'Post not found'}), 404

    if row['author_id'] != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403

    # Build XML safely using the element tree API — no string interpolation
    data_el = etree.Element('data')
    posts_el = etree.SubElement(data_el, 'posts')
    post_el = etree.SubElement(posts_el, 'post')

    title_el = etree.SubElement(post_el, 'post_title')
    title_el.text = row['title']

    content_el = etree.SubElement(post_el, 'post_content')
    content_el.text = row['content']

    category_el = etree.SubElement(post_el, 'post_category')
    category_el.text = row['category']

    status_el = etree.SubElement(post_el, 'post_status')
    status_el.text = row['status']

    xml_bytes = etree.tostring(data_el, pretty_print=True, xml_declaration=True, encoding='UTF-8')

    return xml_bytes, 200, {
        'Content-Type': 'application/xml',
        'Content-Disposition': f'attachment; filename="post_{post_id}.xml"'
    }
