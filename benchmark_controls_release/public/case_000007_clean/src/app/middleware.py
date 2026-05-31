import time
import logging
from flask import request, g, session

logger = logging.getLogger("toolforge.access")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


def register_middleware(app):
    @app.before_request
    def start_timer():
        g.start_time = time.monotonic()

    @app.after_request
    def log_request(response):
        duration = int((time.monotonic() - g.get("start_time", time.monotonic())) * 1000)
        user = session.get("username", "-")
        logger.info(
            "%s %s %s %dms user=%s",
            request.method,
            request.path,
            response.status_code,
            duration,
            user,
        )
        return response