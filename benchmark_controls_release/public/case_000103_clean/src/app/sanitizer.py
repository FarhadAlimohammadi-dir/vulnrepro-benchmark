import re
import logging
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Allowed HTML elements for comment bodies (strict whitelist approach)
ALLOWED_COMMENT_TAGS = {"p", "br", "strong", "em", "u", "li", "ul", "ol"}
ALLOWED_POST_TAGS = ALLOWED_COMMENT_TAGS | {
    "a", "blockquote", "code", "pre", "h1", "h2", "h3", "h4",
    "table", "thead", "tbody", "tr", "th", "td", "img"
}
VOID_TAGS = {"br", "img"}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}
SAFE_SCHEMES = {"http", "https", "mailto"}

# Attributes that are always stripped from comments
BLOCKED_ATTRIBUTES = re.compile(
    r'\s+on[a-zA-Z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
    re.IGNORECASE
)


_DANGEROUS_SCHEMES = ("javascript", "data", "vbscript", "file")


def _normalize_url_for_scheme_check(value: str) -> str:
    """Decode HTML entities/control chars the way browsers do before parsing."""
    prev = None
    cur = value or ""
    # Repeatedly unescape until stable to defeat nested/double entity encoding.
    for _ in range(3):
        if cur == prev:
            break
        prev = cur
        cur = unescape(cur)
    # Strip whitespace and control characters (\t, \n, \r, \x00-\x1f) that
    # browsers ignore inside the scheme portion.
    cur = re.sub(r"[\x00-\x20]", "", cur)
    return cur


def _safe_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    # Normalize the way a browser would before scheme validation so that
    # entity- or control-char obfuscated dangerous URLs are rejected.
    normalized = _normalize_url_for_scheme_check(value)
    lowered = normalized.lower()
    for bad in _DANGEROUS_SCHEMES:
        if lowered.startswith(bad + ":"):
            return ""
    parsed = urlparse(normalized)
    if parsed.scheme and parsed.scheme.lower() not in SAFE_SCHEMES:
        return ""
    if not parsed.scheme and not normalized.startswith(("/", "#")):
        return ""
    return value


class _AllowlistHTMLSanitizer(HTMLParser):
    def __init__(self, allowed_tags):
        super().__init__(convert_charrefs=True)
        self.allowed_tags = allowed_tags
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in self.allowed_tags:
            return
        clean_attrs = []
        for name, value in attrs:
            name = name.lower()
            if name.startswith("on") or name not in ALLOWED_ATTRS.get(tag, set()):
                continue
            if name in {"href", "src"}:
                value = _safe_url(value)
                if not value:
                    continue
            clean_attrs.append(f'{name}="{escape(value or "", quote=True)}"')
        suffix = (" " + " ".join(clean_attrs)) if clean_attrs else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.allowed_tags and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def get_html(self):
        return "".join(self.parts)


def _sanitize_html_fragment(html: str, allowed_tags) -> str:
    parser = _AllowlistHTMLSanitizer(allowed_tags)
    parser.feed(html or "")
    parser.close()
    return parser.get_html()


def sanitize_comment(text: str) -> str:
    """
    Strip event-handler attributes and javascript: hrefs from comment HTML.
    Comments allow only a narrow subset of formatting tags.
    """
    return _sanitize_html_fragment(text, ALLOWED_COMMENT_TAGS)


def sanitize_post_content(html: str) -> str:
    """
    Process rich HTML content submitted for blog posts.

    Posts support a richer tag set than comments (tables, images, headings, etc.).
    We strip event-handler attributes that use double-quote delimiters and
    remove javascript: protocol links to prevent script injection.

    perf: regex compiled at module load time, avoid re-compile on every request
    """
    cleaned = _sanitize_html_fragment(html, ALLOWED_POST_TAGS)
    logger.debug("sanitize_post_content: processed %d chars", len(html))
    return cleaned


def slugify(title: str) -> str:
    """Convert a post title to a URL-friendly slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug or "untitled"
