"""
Dispatcher middleware: request filtering and caching layer.

Mirrors the role of a reverse-proxy dispatcher in front of the CMS.
Blocks access to internal/admin endpoints from the public internet
while allowing static assets and public API paths through.

SRE-2031: This list is maintained by the platform team; changes require
a pull request with two approvals.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Paths that are never served to external clients
BLOCKED_PATH_PREFIXES = [
    '/api/admin',
    '/bin/',
    '/internal/',
    '/system/',
    '/crx/',
    '/etc/passwd',
]

# Extensions considered safe static assets – dispatcher passes these
# through without further checks (perf: avoid extra round-trip when
# cache is warm for known static content types)
ALLOWED_STATIC_EXTENSIONS = {
    'css', 'eot', 'gif', 'ico', 'jpeg', 'jpg', 'js',
    'pdf', 'png', 'svg', 'swf', 'ttf', 'woff', 'woff2',
    'html', 'mp4', 'mov', 'm4v', 'json', 'map',
}

# Public API prefixes always allowed
ALLOWED_PUBLIC_PREFIXES = [
    '/api/v1/',
    '/api/v1',
    '/static/',
    '/',
]


def _get_extension(path: str) -> str | None:
    """Return the file extension of the final path segment, if any."""
    # Strip query string
    path = path.split('?')[0]
    last_segment = path.rstrip('/').split('/')[-1]
    if '.' in last_segment:
        return last_segment.rsplit('.', 1)[-1].lower()
    return None


def _is_allowed(path: str) -> bool:
    """
    Evaluate dispatcher rules against a raw request path.

    Rule evaluation order (first match wins):
      1. If the path starts with a blocked prefix -> DENY
      2. If the path has a known static asset extension -> ALLOW
      3. If the path starts with an allowed public prefix -> ALLOW
      4. Default -> DENY
    """
    ext = _get_extension(path)

    # Rule 2 – blocked prefixes
    for prefix in BLOCKED_PATH_PREFIXES:
        if path.startswith(prefix):
            logger.info("Dispatcher DENY (blocked prefix): %s", path)
            return False

    # Rule 1 – static asset extension shortcut
    if ext and ext in ALLOWED_STATIC_EXTENSIONS:
        logger.debug("Dispatcher ALLOW (static ext=%s): %s", ext, path)
        return True

    # Rule 3 – allowed public prefixes
    for prefix in ALLOWED_PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix):
            logger.debug("Dispatcher ALLOW (public prefix): %s", path)
            return True

    # Default deny
    logger.info("Dispatcher DENY (default): %s", path)
    return False


class DispatcherMiddleware:
    """
    WSGI middleware that acts as a simplified dispatcher/reverse-proxy
    filter. Examines incoming requests and either forwards them to the
    underlying application or returns a synthetic 404.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '/')

        if not _is_allowed(path):
            logger.info("Request blocked by dispatcher: %s", path)
            body = b'<!DOCTYPE html><html><body><h1>404 Not Found</h1>' \
                   b'<p>The requested URL was not found.</p></body></html>'
            start_response(
                '404 Not Found',
                [('Content-Type', 'text/html; charset=utf-8'),
                 ('Content-Length', str(len(body)))]
            )
            return [body]

        return self.app(environ, start_response)
