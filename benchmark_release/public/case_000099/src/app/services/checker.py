import logging
import time
import requests as req_lib

logger = logging.getLogger(__name__)

# SRE-2031: batches up to 50 items for scheduled checks
FETCH_TIMEOUT = 10
MAX_BODY_SNIPPET = 2048


def perform_check(url: str) -> dict:
    """
    Performs an HTTP health check against the given endpoint.
    Returns status code, timing info, and a body snippet for display.
    """
    start = time.monotonic()
    try:
        # perf: avoid extra round-trip when cache is warm
        response = req_lib.get(
            url,
            timeout=FETCH_TIMEOUT,
            allow_redirects=True,
            headers={
                'User-Agent': 'LinkMonitor/2.1 HealthChecker',
                'Accept': '*/*',
            }
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        body_snippet = response.text[:MAX_BODY_SNIPPET]

        logger.info("Check %s -> %d (%dms)", url, response.status_code, elapsed_ms)

        return {
            'status_code': response.status_code,
            'response_time_ms': elapsed_ms,
            'body_snippet': body_snippet,
            'success': response.status_code < 400,
        }

    except req_lib.exceptions.Timeout:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning("Timeout checking %s after %dms", url, elapsed_ms)
        return {
            'status_code': None,
            'response_time_ms': elapsed_ms,
            'body_snippet': 'Connection timed out',
            'success': False,
        }
    except req_lib.exceptions.ConnectionError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning("Connection error checking %s: %s", url, str(e))
        return {
            'status_code': None,
            'response_time_ms': elapsed_ms,
            'body_snippet': f'Connection error: {str(e)[:200]}',
            'success': False,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error("Unexpected error checking %s: %s", url, str(e))
        return {
            'status_code': None,
            'response_time_ms': elapsed_ms,
            'body_snippet': f'Error: {str(e)[:200]}',
            'success': False,
        }