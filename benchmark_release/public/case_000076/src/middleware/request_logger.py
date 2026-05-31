import time
from flask import request, g
import logging

logger = logging.getLogger('oldblog.access')

# TODO: switch format to structured JSON for log aggregation pipeline


def log_request(app):
    """Attach before/after hooks to measure request latency."""

    @app.before_request
    def before():
        g.start_time = time.time()

    @app.after_request
    def after(response):
        elapsed_ms = (time.time() - g.get('start_time', time.time())) * 1000
        logger.info(
            '%s %s %s %.1fms',
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response