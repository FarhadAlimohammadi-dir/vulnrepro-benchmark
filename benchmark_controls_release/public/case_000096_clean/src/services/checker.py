import json
import time
import logging
import socket
import ipaddress
import threading
from contextlib import contextmanager
from urllib.parse import urlparse
import requests as http_client
from requests.exceptions import RequestException, Timeout, ConnectionError

# Thread-local store mapping hostname -> list of pre-validated addrinfos.
# socket.getaddrinfo is monkey-patched inside _pinned_dns() so all DNS
# resolution performed by requests/urllib3 during a check resolves to the
# addresses we already verified, eliminating DNS-rebinding between the
# validation step and the actual HTTP request.
_PIN_LOCK = threading.Lock()
_PIN_TLS = threading.local()
_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _patched_getaddrinfo(host, port, *args, **kwargs):
    pins = getattr(_PIN_TLS, 'pins', None)
    if pins and host in pins:
        # Rewrite each cached infotuple to include the requested port.
        rewritten = []
        for af, st, proto, canon, sockaddr in pins[host]:
            if af == socket.AF_INET6:
                rewritten.append((af, st, proto, canon, (sockaddr[0], port or 0, 0, 0)))
            else:
                rewritten.append((af, st, proto, canon, (sockaddr[0], port or 0)))
        return rewritten
    return _ORIGINAL_GETADDRINFO(host, port, *args, **kwargs)


@contextmanager
def _pinned_dns(host, infos):
    """Pin DNS resolution for `host` to the given addrinfos for this call."""
    with _PIN_LOCK:
        if socket.getaddrinfo is not _patched_getaddrinfo:
            socket.getaddrinfo = _patched_getaddrinfo
    prev = getattr(_PIN_TLS, 'pins', None) or {}
    new = dict(prev)
    new[host] = infos
    _PIN_TLS.pins = new
    try:
        yield
    finally:
        _PIN_TLS.pins = prev

logger = logging.getLogger(__name__)

# Maximum response body size to store (bytes)
MAX_BODY_SIZE = 8192

# Headers that the user must not be able to inject — they could be used to
# satisfy header-based authentication on internal services.
_FORBIDDEN_USER_HEADERS = {
    'host', 'x-metadata-flavor', 'metadata-flavor',
    'x-internal-auth', 'x-forwarded-for', 'x-real-ip',
    'authorization',
}


def _ip_is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_safe_addresses(url: str):
    """Return (host, list_of_safe_addrinfos) when the URL is safe, else (None, None).

    Used by callers that want to both validate *and* pin the resolved IPs
    onto the actual HTTP request, closing the DNS-rebinding gap between
    validation and request.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None, None
    host = (parsed.hostname or '').lower()
    if not host:
        return None, None
    # If the literal hostname is itself an IP, check it directly.
    try:
        if _ip_is_private(host):
            return None, None
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None, None
    if not infos:
        return None, None
    for info in infos:
        ip = info[4][0]
        if _ip_is_private(ip):
            return None, None
    return host, infos


def _is_blocked_url(url: str) -> bool:
    host, infos = _resolve_safe_addresses(url)
    return host is None


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
    host, safe_infos = _resolve_safe_addresses(url)
    if host is None:
        return {
            'status': 'error',
            'error_message': 'Target URL is not allowed',
            'response_code': None,
            'response_time_ms': None,
            'response_body': '',
        }

    headers = {
        'User-Agent': 'PulseCheck-Monitor/1.0',
        'Accept': '*/*',
    }
    # Merge user-supplied headers - allows custom auth and content-type headers
    # legacy: kept for v1 API clients still in the wild
    if isinstance(custom_headers, dict):
        for hk, hv in custom_headers.items():
            if not isinstance(hk, str):
                continue
            if hk.lower() in _FORBIDDEN_USER_HEADERS:
                # Silently drop headers that could be used to authenticate
                # against internal services.
                continue
            headers[hk] = hv

    start_time = time.time()
    try:
        # Disable redirects to prevent redirect-based SSRF bypass; the
        # destination has already been validated to be a public address.
        # Pin DNS for the duration of the call so urllib3 cannot resolve a
        # different (private) address than the one we just validated.
        with _pinned_dns(host, safe_infos):
            if method == 'HEAD':
                resp = http_client.head(url, headers=headers, timeout=timeout, allow_redirects=False)
            elif method == 'POST':
                resp = http_client.post(url, headers=headers, timeout=timeout, allow_redirects=False)
            else:
                resp = http_client.get(url, headers=headers, timeout=timeout, allow_redirects=False)

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
    if _is_blocked_url(url):
        return False, 'Target URL is not allowed'
    if method not in ('GET', 'POST', 'HEAD'):
        return False, 'Method must be GET, POST, or HEAD'
    return True, ''
