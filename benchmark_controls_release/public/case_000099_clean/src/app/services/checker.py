import logging
import os
import time
from urllib.parse import urlparse
import ipaddress
import socket
import requests as req_lib

logger = logging.getLogger(__name__)

# SRE-2031: batches up to 50 items for scheduled checks
FETCH_TIMEOUT = 10
MAX_BODY_SNIPPET = 2048
ALLOWED_MONITOR_HOSTS = {
    host.strip().lower()
    for host in os.environ.get('ALLOWED_MONITOR_HOSTS', 'example.com,httpbin.org,statuspage.io').split(',')
    if host.strip()
}


def _target_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        return False
    host = (parsed.hostname or '').lower()
    if not host:
        return False
    if host not in ALLOWED_MONITOR_HOSTS:
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for info in infos:
        address = info[4][0]
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def perform_check(url: str) -> dict:
    """
    Performs an HTTP health check against the given endpoint.
    Returns status code, timing info, and a body snippet for display.
    """
    start = time.monotonic()
    if not _target_allowed(url):
        return {
            'status_code': None,
            'response_time_ms': 0,
            'body_snippet': 'Target URL is not allowed',
            'success': False,
        }
    try:
        # perf: avoid extra round-trip when cache is warm
        response = req_lib.get(
            url,
            timeout=FETCH_TIMEOUT,
            allow_redirects=False,
            headers={
                'User-Agent': 'LinkMonitor/2.1 HealthChecker',
                'Accept': '*/*',
            }
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if 300 <= response.status_code < 400:
            body_snippet = 'Redirect response was not followed'
        else:
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
