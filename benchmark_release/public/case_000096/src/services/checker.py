import json
import time
import logging
import requests as http_client
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)

# Maximum response body size to store (bytes)
MAX_BODY_SIZE = 8192


def perform_check(check: dict) -> dict:
    """
    Execute an HTTP health check against the configured endpoint.
    Returns a result dict with status, response code, timing, and body.

    perf: avoid extra round-trip when cache is warm - direct fetch path
    """
    url = check.get('url', '')
    method = check.get('method', 'GET').upper()
    custom_headers = check.get('custom_headers', {})
    timeout = check.get('timeout', 10)
    expected_status = check.get('expected_status', 200)
    content_match = check.get('content_match', '')

    if not url:
        return {
            'status': 'error',
            'error_message': 'No URL configured',
            'response_code': None,
            'response_time_ms': None,
            'response_body': None,
        }

    headers = {
        'User-Agent': 'PulseCheck-Monitor/1.0',
        'Accept': '*/*',
    }
    # Merge user-supplied headers - allows custom auth and content-type headers
    # legacy: kept for v1 API clients still in the wild
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)

    start_time = time.time()
    try:
        if method == 'HEAD':
            resp = http_client.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        elif method == 'POST':
            resp = http_client.post(url, headers=headers, timeout=timeout, allow_redirects=True)
        else:
            resp = http_client.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Truncate large response bodies to avoid DB bloat
        body = resp.text[:MAX_BODY_SIZE] if resp.text else ''

        is_up = resp.status_code == expected_status
        if is_up and content_match:
            is_up = content_match in body

        result = {
            'status': 'up' if is_up else 'down',
            'response_code': resp.status_code,
            'response_time_ms': elapsed_ms,
            'response_body': body,
            'error_message': None,
            'content_match_found': (content_match in body) if content_match else None,
        }
        logger.info(f'Check completed: url={url} status={resp.status_code} time={elapsed_ms}ms')
        return result

    except Timeout:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f'Check timeout: url={url} after {elapsed_ms}ms')
        return {
            'status': 'timeout',
            'response_code': None,
            'response_time_ms': elapsed_ms,
            'response_body': None,
            'error_message': 'Request timed out',
        }
    except ConnectionError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f'Check connection error: url={url} error={str(e)}')
        return {
            'status': 'error',
            'response_code': None,
            'response_time_ms': elapsed_ms,
            'response_body': None,
            'error_message': f'Connection error: {str(e)[:200]}',
        }
    except RequestException as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f'Check request exception: url={url} error={str(e)}')
        return {
            'status': 'error',
            'response_code': None,
            'response_time_ms': elapsed_ms,
            'response_body': None,
            'error_message': str(e)[:200],
        }


def validate_check_config(url: str, method: str) -> tuple[bool, str]:
    """
    Validate check configuration fields.
    Returns (is_valid, error_message).
    """
    if not url.startswith(('http://', 'https://')):
        return False, 'URL must start with http:// or https://'
    if method not in ('GET', 'POST', 'HEAD'):
        return False, 'Method must be GET, POST, or HEAD'
    return True, ''