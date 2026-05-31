"""
HTML content cleaning service.

Processes rich-text HTML from the editor before storage and display.
Uses bleach for tag/attribute allow-listing.
"""

import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Tags allowed in rich text notes
ALLOWED_TAGS = [
    "p", "br", "b", "i", "strong", "em", "u", "s",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "pre", "code",
    "a", "img",
    "div", "span",
    "hr",
]

ALLOWED_URL_SCHEMES = ("http", "https", "mailto")
ALLOWED_IMG_SCHEMES = ("http", "https")


def _safe_href(value):
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("/") or candidate.startswith("#"):
        return candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    scheme = (parsed.scheme or "").lower()
    if scheme and scheme not in ALLOWED_URL_SCHEMES:
        return None
    if not scheme and not parsed.netloc:
        return candidate
    return candidate


def _safe_src(value):
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("/"):
        return candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    scheme = (parsed.scheme or "").lower()
    if scheme and scheme not in ALLOWED_IMG_SCHEMES:
        return None
    return candidate


def _attr_filter(tag, name, value):
    if tag == "a":
        if name == "href":
            return _safe_href(value) is not None
        return name in ("title",)
    if tag == "img":
        if name == "src":
            return _safe_src(value) is not None
        return name in ("alt", "width", "height")
    if tag == "table":
        return name in ("border", "cellpadding", "cellspacing")
    if tag in ("td", "th"):
        return name in ("colspan", "rowspan")
    if tag in ("div", "span", "p"):
        return name == "class"
    return False


def clean_html(raw_html: str) -> str:
    """
    Cleans user-supplied rich text HTML.

    Strips disallowed tags and attributes. Intended to produce safe HTML
    for embedding in the note preview renderer.
    """
    if not raw_html:
        return ""

    try:
        import bleach
        cleaned = bleach.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=_attr_filter,
            protocols=list(ALLOWED_URL_SCHEMES),
            strip=True,
            strip_comments=True,
        )
        try:
            cleaned = bleach.linkify(
                cleaned,
                callbacks=[
                    lambda attrs, new=False: {**attrs, (None, "rel"): "noopener noreferrer", (None, "target"): "_blank"},
                ],
                skip_tags=["pre", "code"],
            )
        except Exception:
            pass
        return cleaned
    except Exception as exc:
        logger.error("HTML cleaning error: %s", exc)
        return ""
