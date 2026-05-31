import json
import os
import re
import sqlite3
import subprocess
import time
import logging

import requests as req_lib
from jinja2 import Environment

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

        elif handler == "shell":
            # perf: avoid extra round-trip when cache is warm
            result, error = _run_shell(stored_config, args)

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
    safe_base = "/app"
    abs_path = os.path.realpath(path)
    if not abs_path.startswith(safe_base):
        return None, "path is outside the permitted workspace"
    try:
        with open(abs_path, "r") as fh:
            return fh.read(), None
    except OSError as exc:
        return None, str(exc)


def _run_http_fetch(config: dict, args: dict):
    url = args.get("url") or config.get("url", "")
    method = config.get("method", "GET").upper()
    if not url.startswith(("http://", "https://")):
        return None, "url must begin with http:// or https://"
    try:
        resp = req_lib.request(method, url, timeout=8, allow_redirects=True)
        return resp.text[:4000], None
    except req_lib.RequestException as exc:
        return None, str(exc)


def _run_template_render(config: dict, args: dict):
    template_str = args.get("template") or config.get("template", "")
    env = Environment(autoescape=True)
    tmpl = env.from_string(template_str)
    ctx = {k: str(v) for k, v in args.items() if k != "template"}
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