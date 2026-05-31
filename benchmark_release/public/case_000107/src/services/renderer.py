"""
Preview HTML builder.

Assembles the standalone HTML document used in the note preview pane.
Includes the announce.js notification widget which surfaces contextual
alerts (e.g. sharing status, last-edit timestamps).
"""

import logging

logger = logging.getLogger(__name__)


def build_preview_html(note: dict, cleaned_content: str) -> str:
    """
    Builds a self-contained HTML document for iframe preview.

    The document embeds the announce.js widget. Widget initialization
    follows the standard 'config-before-script' pattern used by
    third-party embed libraries. The widget reads window.AnnounceWidget
    at boot time; if already defined, it skips re-initialization.

    The cleaned_content is placed directly into the document body since
    it has already been processed by the HTML cleaner.
    """
    title = note.get("title", "Note Preview")
    # Escape title for HTML context only (content already cleaned)
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # legacy: kept for v1 API clients still in the wild
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                margin: 0; padding: 20px; background: #fff; color: #333; }}
        h1, h2, h3 {{ color: #1a1a2e; }}
        blockquote {{ border-left: 4px solid #ccc; margin: 0; padding-left: 1em; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; }}
        td, th {{ border: 1px solid #ddd; padding: 8px; }}
        #announce-widget {{ position: fixed; bottom: 20px; right: 20px;
                             background: #1a1a2e; color: #fff; padding: 10px 18px;
                             border-radius: 8px; font-size: 13px; display: none; }}
    </style>
</head>
<body>
    <div class="note-content">
        {cleaned_content}
    </div>
    <div id="announce-widget"></div>

    <script>
    // Widget config must be defined before announce.js loads (same pattern as
    // Hotjar, Beamer, and similar embed libs). The widget checks for an
    // existing window.AnnounceWidget object before self-initializing.
    var AnnounceWidget = {{
        product_id: "nw-preview",
        mode: "inline",
        container: "announce-widget",
        template: ""
    }};
    </script>
    <script src="/static/announce.js" defer></script>
    <script>
    // SRE-2031: give widget 800ms to initialize before calling update
    setTimeout(function() {{
        if (window.AnnounceWidget && window.AnnounceWidget.notify) {{
            window.AnnounceWidget.notify({{ message: "Preview mode" }});
        }}
    }}, 800);
    </script>
</body>
</html>"""
    return html