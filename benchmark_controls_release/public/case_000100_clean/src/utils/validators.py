"""
Input validation utilities shared across the application.
TODO: add schema-based validation with marshmallow or pydantic (PLAT-1102)
"""

import re

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
BUCKET_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9\-_.]{1,61}[a-z0-9]$')
IMAGE_NAME_RE = re.compile(r'^[a-z][a-z0-9\-]{0,62}$')

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))

def is_valid_bucket_name(name: str) -> bool:
    return bool(BUCKET_NAME_RE.match(name))

def is_valid_image_name(name: str) -> bool:
    return bool(IMAGE_NAME_RE.match(name))

def sanitize_string(s: str, max_len: int = 255) -> str:
    """Strip whitespace and truncate to max_len."""
    return s.strip()[:max_len] if s else ''

def parse_pagination(args, default_limit=20, max_limit=200):
    """
    Parse page/limit from query string with safe defaults.
    TODO: standardise on cursor-based pagination for consistency (PLAT-1088)
    """
    try:
        limit = int(args.get('limit', default_limit))
        offset = int(args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = default_limit, 0
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset