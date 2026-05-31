"""
/bin/ endpoint – internal query interface.
Blocked by the dispatcher for external clients.
"""
import logging
from flask import Blueprint, request, jsonify
from db import get_db

logger = logging.getLogger(__name__)
bin_bp = Blueprint('bin', __name__)


@bin_bp.route('/querybuilder', methods=['GET'])
@bin_bp.route('/querybuilder.json', methods=['GET'])
@bin_bp.route('/querybuilder.<suffix>', methods=['GET'])
def querybuilder(suffix=None):
    """
    Node/content query interface. Returns structured content data
    matching the provided filters. Used by the authoring UI and
    content synchronisation pipelines.
    """
    db = get_db()
    node_type = request.args.get('type', 'article')
    path_prefix = request.args.get('path', '/content/')
    limit = min(int(request.args.get('limit', 20)), 100)

    rows = db.execute(
        "SELECT id, title, slug, category, status, published_at "
        "FROM articles ORDER BY id LIMIT ?",
        (limit,)
    ).fetchall()

    result = {
        'hits': [dict(r) for r in rows],
        'total': len(rows),
        'queryParameters': {
            'type': node_type,
            'path': path_prefix,
        }
    }
    logger.info("Querybuilder accessed from %s", request.remote_addr)
    return jsonify(result)