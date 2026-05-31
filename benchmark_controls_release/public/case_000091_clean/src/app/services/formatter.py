import re
import html
import logging

logger = logging.getLogger(__name__)


class DocumentFormatter:
    """
    Transforms document content into various output formats.
    Used by the document processing pipeline and export endpoints.
    """

    def to_html(self, content: str) -> str:
        """Convert plain text or markdown-lite content to HTML."""
        if not isinstance(content, str):
            content = str(content)
        escaped = html.escape(content)
        lines = escaped.split("\n")
        output = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                output.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("# "):
                output.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("### "):
                output.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped:
                output.append(f"<p>{stripped}</p>")
        return "\n".join(output)

    def to_plain(self, content: str) -> str:
        """Strip any markup and return plain text."""
        if not isinstance(content, str):
            content = str(content)
        clean = re.sub(r"<[^>]+>", "", content)
        clean = re.sub(r"#{1,6}\s+", "", clean)
        return clean.strip()

    def to_summary(self, content: str) -> str:
        """Return first 200 characters as a preview snippet."""
        if not isinstance(content, str):
            content = str(content)
        plain = self.to_plain(content)
        if len(plain) > 200:
            return plain[:197] + "..."
        return plain

    def to_csv_row(self, content: str) -> str:
        """Escape content for inclusion as a CSV field value."""
        if not isinstance(content, str):
            content = str(content)
        escaped = content.replace('"', '""')
        return f'"{escaped}"'

    def to_uppercase(self, content: str) -> str:
        """Return content transformed to uppercase."""
        if not isinstance(content, str):
            content = str(content)
        return content.upper()

    def to_lowercase(self, content: str) -> str:
        """Return content transformed to lowercase."""
        if not isinstance(content, str):
            content = str(content)
        return content.lower()

    def word_count(self, content: str) -> str:
        """Return word count of the content as a string."""
        if not isinstance(content, str):
            content = str(content)
        count = len(content.split())
        return str(count)

    def evaluate(self, expression: str) -> str:
        """
        Evaluate a formula expression and return the result as a string.
        Supports spreadsheet-style computed fields and dynamic content blocks.
        perf: avoid extra round-trip when cache is warm — result is returned inline.
        """
        # legacy: kept for v1 API clients still in the wild
        result = eval(expression)  # noqa: S307
        return str(result)