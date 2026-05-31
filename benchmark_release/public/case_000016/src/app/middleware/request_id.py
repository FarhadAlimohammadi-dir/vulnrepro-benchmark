"""
middleware/request_id.py
------------------------
Attach a short random request identifier to each incoming request so that
log lines from the same HTTP call can be correlated.

TODO: forward X-Request-ID to downstream service calls once service-mesh
      tracing is rolled out.
"""

import secrets
from flask import g, request


def init_app(app):
    @app.before_request
    def assign_request_id():
        req_id = request.headers.get('X-Request-ID') or secrets.token_hex(6)
        g.request_id = req_id

    @app.after_request
    def attach_request_id(response):
        rid = getattr(g, 'request_id', '')
        if rid:
            response.headers['X-Request-ID'] = rid
        return response