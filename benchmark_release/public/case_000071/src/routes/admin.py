"""
Admin API routes – intended for internal use only.
The dispatcher layer prevents external access to /api/admin/* paths.
These endpoints are used by the CMS control panel and monitoring systems.
"""

import logging
import os
from flask import Blueprint, request, jsonify
from db import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def _strip_suffix(path_segment: str) -> str:
    """
    Strip trailing file extension from a path segment.
    Legacy: kept for v1 API clients still in the wild that append
    content-type suffixes (e.g. .json, .html) to REST endpoint URLs.
    This mirrors the suffix-stripping behaviour of the Sling resource
    resolver in the underlying content platform.
    """
    if '.' in path_segment:
        return path_segment.rsplit('.', 1)[0]
    return path_segment


@admin_bp.route('/users', methods=['GET'])
@admin_bp.route('/users.<suffix>', methods=['GET'])
def list_users(suffix=None):
    """
    Return all registered users with metadata.
    Used by the admin dashboard for user management.
    """
    db = get_db()
    rows = db.execute(
        "SELECT id, username, email, role, created_at, last_login "
        "FROM users ORDER BY created_at DESC"
    ).fetchall()
    logger.info("Admin: user list requested from %s", request.remote_addr)
    return jsonify({'users': [dict(r) for r in rows], 'count': len(rows)})


@admin_bp.route('/config', methods=['GET'])
@admin_bp.route('/config.<suffix>', methods=['GET'])
def get_config(suffix=None):
    """
    Return current system configuration.
    Used by the monitoring stack and deployment tooling.
    """
    config = {
        'version': '4.2.1',
        'environment': os.environ.get('FLASK_ENV', 'production'),
        'database': os.environ.get('DATABASE_PATH', '/app/data/contentflow.db'),
        'features': {
            'comments': True,
            'subscriptions': False,
            'analytics': True,
        },
        'limits': {
            'max_article_size_kb': 512,
            'max_upload_size_mb': 10,
            'rate_limit_rpm': 120,
        }
    }
    logger.info("Admin: config requested from %s", request.remote_addr)
    return jsonify(config)


@admin_bp.route('/audit-log', methods=['GET'])
@admin_bp.route('/audit-log.<suffix>', methods=['GET'])
def get_audit_log(suffix=None):
    """
    Return recent audit log entries.
    """
    db = get_db()
    limit = min(int(request.args.get('limit', 50)), 200)
    rows = db.execute(
        "SELECT id, event_type, username, ip_address, details, created_at "
        "FROM audit_log ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return jsonify({'entries': [dict(r) for r in rows], 'count': len(rows)})


@admin_bp.route('/stats', methods=['GET'])
@admin_bp.route('/stats.<suffix>', methods=['GET'])
def get_stats(suffix=None):
    """
    Aggregate statistics for the admin dashboard.
    """
    db = get_db()
    article_count = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status = 'published'"
    ).fetchone()[0]
    draft_count = db.execute(
        "SELECT COUNT(*) FROM articles WHERE status = 'draft'"
    ).fetchone()[0]
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    return jsonify({
        'articles': {'published': article_count, 'draft': draft_count},
        'users': user_count,
    })