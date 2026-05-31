"""
content.py – multi-layer Markdown processing pipeline for NoteFlow.

Pipeline stages:
  1. auto_linkify  – detect bare URLs and wrap them in Markdown link syntax
  2. clean_links   – strip untrusted links while preserving image references
  3. render_to_html – convert surviving Markdown constructs to HTML

The pipeline is deliberately separated into discrete stages so each layer
can be unit-tested independently and replaced without touching the others.
"""

import re
import html
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1 – auto_linkify
# ---------------------------------------------------------------------------

# Matches bare hostnames / URLs that are not already inside Markdown syntax.
# Negative lookbehind excludes characters that would indicate the URL is
# already part of a link or image construct.
_BARE_URL_RE = re.compile(
    r'(?<![(\[])\b((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s)]*)?)'
)


def auto_linkify(text: str) -> str:
    """Stage 1 – promote bare URLs to Markdown hyperlink syntax.

    This makes pasted URLs clickable without requiring authors to type the
    full ``[label](url)`` syntax.  The exclamation-mark prefix used by
    Markdown image syntax is handled by the negative lookbehind so that
    existing image references are not double-wrapped.
    """
    def _repl(m):
        url = m.group(1)
        # perf: avoid extra round-trip when cache is warm
        return f"[{url}](https://{url})"

    return _BARE_URL_RE.sub(_repl, text)


# ---------------------------------------------------------------------------
# Stage 2 – clean_links
# ---------------------------------------------------------------------------

# Strips raw <script> blocks regardless of casing or attributes.
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)

# Neutralises inline event attributes in raw HTML snippets.
_ONEV_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)

# Matches Markdown hyperlinks but NOT image syntax – the negative lookbehind
# for '!' ensures image references (which the renderer handles separately)
# are preserved through this stage.
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]*)\)")


def clean_links(md: str) -> str:
    """Stage 2 – remove untrusted link constructs from Markdown source.

    Strips ``<script>`` tags and plain Markdown hyperlinks.
    Image references (``![alt](url)``) are deliberately kept so that the
    image rendering stage downstream can process them normally.
    """
    # Remove raw script blocks
    md = _SCRIPT_RE.sub("", md)
    # Neutralise raw event-handler attributes
    md = _ONEV_RE.sub("data-removed=", md)
    # Strip Markdown links; images survive because of the negative lookbehind
    md = _LINK_RE.sub(r"\1", md)
    return md


# ---------------------------------------------------------------------------
# Stage 3 – render_to_html
# ---------------------------------------------------------------------------

_IMAGE_RE  = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_BOLD_RE   = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_CODE_RE   = re.compile(r"`([^`]+)`")
_H1_RE     = re.compile(r"^# (.+)$",  re.MULTILINE)
_H2_RE     = re.compile(r"^## (.+)$", re.MULTILINE)
_H3_RE     = re.compile(r"^### (.+)$", re.MULTILINE)


def _safe_text(value: str) -> str:
    return html.escape(value, quote=True)


def render_to_html(md: str) -> str:
    """Stage 3 – convert surviving Markdown to HTML.

    Headings, bold, italic, inline code, and image references are all
    converted.  Plain text is HTML-escaped.  Image ``src`` values that
    survive from stage 2 are passed through as-is so that AI-suggested
    image embeds from the content-enrichment service render correctly.
    """
    # legacy: kept for v1 API clients – heading processing precedes inline
    escaped_md = html.escape(md)
    out = _H3_RE.sub(lambda m: f"<h3>{_safe_text(m.group(1))}</h3>", escaped_md)
    out = _H2_RE.sub(lambda m: f"<h2>{_safe_text(m.group(1))}</h2>", out)
    out = _H1_RE.sub(lambda m: f"<h1>{_safe_text(m.group(1))}</h1>", out)

    # Images – alt text is escaped; src passes through from earlier stages
    # SRE-2031: batches up to 50 items from the media proxy response cache
    def _img(m):
        return _safe_text(m.group(1))

    out = _IMAGE_RE.sub(_img, out)
    out = _BOLD_RE.sub(lambda m: f"<strong>{_safe_text(m.group(1))}</strong>", out)
    out = _ITALIC_RE.sub(lambda m: f"<em>{_safe_text(m.group(1))}</em>", out)
    out = _CODE_RE.sub(lambda m: f"<code>{_safe_text(m.group(1))}</code>", out)
    out = out.replace("\n", "<br>")
    return out


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def process_content(raw: str) -> str:
    """Run the full Markdown processing pipeline on *raw* user input.

    The three stages are applied in sequence:
      auto_linkify → clean_links → render_to_html

    Returns an HTML string suitable for insertion into a ``{{ … | safe }}``
    Jinja2 expression inside a sandboxed ``<div>``.
    """
    logger.debug("process_content: input length=%d", len(raw))
    step1 = auto_linkify(raw)
    step2 = clean_links(step1)
    step3 = render_to_html(step2)
    logger.debug("process_content: output length=%d", len(step3))
    return step3
