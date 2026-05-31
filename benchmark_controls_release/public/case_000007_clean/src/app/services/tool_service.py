import json
import os
import re
import sqlite3
import subprocess
import time
import logging
import socket
import ipaddress
import threading
from contextlib import contextmanager
from urllib.parse import urlparse

import requests as req_lib
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger("toolforge.tool_service")

VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')
MAX_NAME_LEN = 64


def validate_tool_name(name: str):
    if not name:
        return "name is required"
    if len(name) > MAX_NAME_LEN:
        return f"name too long (max {MAX_NAME_LEN} chars)"
    if not VALID_NAME_RE.match(name):
        return "name contains invalid characters (a-z, 0-9, _ - only)"
    return None


def execute_handler(handler: str, stored_config: dict, args: dict) -> tuple:
    """
    Dispatch a tool's handler and return (result_text, error_text, duration_ms).
    Supported built-in handlers: read_file, http_fetch, template_render, shell.
    """
    start = time.monotonic()
    result = None
    error = None

    try:
        if handler == "read_file":
            result, error = _run_read_file(stored_config, args)

        elif handler == "http_fetch":
            result, error = _run_http_fetch(stored_config, args)

        elif handler == "template_render":
            result, error = _run_template_render(stored_config, args)

        else:
            error = f"no registered handler for type '{handler}'"

    except Exception as exc:
        logger.exception("Unhandled error in handler '%s'", handler)
        error = str(exc)

    duration_ms = int((time.monotonic() - start) * 1000)
    return result, error, duration_ms


# ── individual runner implementations ────────────────────────────────────────

def _run_read_file(config: dict, args: dict):
    path = args.get("path") or config.get("path", "")
    if not isinstance(path, str) or not path:
        return None, "path is required"
    safe_base = os.path.realpath("/app")
    abs_path = os.path.realpath(path)
    try:
        if os.path.commonpath([safe_base, abs_path]) != safe_base:
            return None, "path is outside the permitted workspace"
    except ValueError:
        return None, "path is outside the permitted workspace"
    try:
        with open(abs_path, "r") as fh:
            return fh.read(), None
    except OSError as exc:
        return None, str(exc)


def _ip_is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_multicast or addr.is_reserved or addr.is_unspecified
    )


def _resolve_safe(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None, None
    host = parsed.hostname.lower()
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
        if _ip_is_private(info[4][0]):
            return None, None
    return host, infos


_HTTP_PIN_LOCK = threading.Lock()
_HTTP_PIN_TLS = threading.local()
_HTTP_ORIG_GETADDRINFO = socket.getaddrinfo


def _http_patched_getaddrinfo(host, port, *args, **kwargs):
    pins = getattr(_HTTP_PIN_TLS, "pins", None)
    if pins and host in pins:
        rewritten = []
        for af, st, proto, canon, sockaddr in pins[host]:
            if af == socket.AF_INET6:
                rewritten.append((af, st, proto, canon, (sockaddr[0], port or 0, 0, 0)))
            else:
                rewritten.append((af, st, proto, canon, (sockaddr[0], port or 0)))
        return rewritten
    return _HTTP_ORIG_GETADDRINFO(host, port, *args, **kwargs)


@contextmanager
def _http_pinned_dns(host, infos):
    with _HTTP_PIN_LOCK:
        if socket.getaddrinfo is not _http_patched_getaddrinfo:
            socket.getaddrinfo = _http_patched_getaddrinfo
    prev = getattr(_HTTP_PIN_TLS, "pins", None) or {}
    new = dict(prev)
    new[host] = infos
    _HTTP_PIN_TLS.pins = new
    try:
        yield
    finally:
        _HTTP_PIN_TLS.pins = prev


# Outbound http_fetch is restricted to a small allowlist of approved business
# endpoints. Generic user-controlled fetch destinations are not permitted.
HTTP_FETCH_ALLOWED_HOSTS = frozenset({
    "api.stripe.com",
    "api.sendgrid.com",
    "hooks.slack.com",
    "api.github.com",
})


def _host_is_allowed(host: str) -> bool:
    if not host:
        return False
    host = host.lower()
    return host in HTTP_FETCH_ALLOWED_HOSTS


def _run_http_fetch(config: dict, args: dict):
    url = args.get("url") or config.get("url", "")
    method = config.get("method", "GET").upper()
    if not isinstance(url, str) or not url.startswith("https://"):
        return None, "url must begin with https://"
    parsed = urlparse(url)
    if not parsed.hostname or not _host_is_allowed(parsed.hostname):
        return None, "url target is not an approved business endpoint"
    if parsed.port not in (None, 443):
        return None, "url target is not an approved business endpoint"
    host, infos = _resolve_safe(url)
    if host is None or not _host_is_allowed(host):
        return None, "url target is not an approved business endpoint"
    try:
        with _http_pinned_dns(host, infos):
            resp = req_lib.request(method, url, timeout=8, allow_redirects=False)
        return resp.text[:4000], None
    except req_lib.RequestException as exc:
        return None, str(exc)


def _run_template_render(config: dict, args: dict):
    # Only the stored (admin-defined) template is rendered. Callers may not
    # override the template source via args, because the template source is
    # treated as trusted code. The args dict supplies *data variables* only.
    template_str = config.get("template", "")
    if not template_str:
        return None, "no template configured for this tool"
    if "template" in args:
        return None, "overriding the template at invoke time is not allowed"
    # SandboxedEnvironment blocks access to unsafe attributes/callables that
    # Jinja sandbox-escape payloads rely on.
    env = SandboxedEnvironment(autoescape=True)
    tmpl = env.from_string(template_str)
    ctx = {k: str(v) for k, v in args.items()}
    return tmpl.render(**ctx), None


def _run_shell(config: dict, args: dict):
    cmd = args.get("cmd", "")
    if not cmd:
        return None, "cmd argument is required"
    try:
        out = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT, timeout=15
        )
        return out.decode(errors="replace"), None
    except subprocess.CalledProcessError as exc:
        return exc.output.decode(errors="replace"), None
    except subprocess.TimeoutExpired:
        return None, "command timed out after 15 seconds"
