import re
import logging
from config import Config

logger = logging.getLogger('nexus.validators')

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{3,32}$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def validate_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username))


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 254


def validate_search_scope(scope: str) -> str | None:
    """Return the scope if it is in the known allowlist, otherwise None."""
    s = (scope or '').strip().lower()
    if s in Config.KNOWN_SEARCH_SCOPES:
        return s
    return None


def validate_conversation_title(title: str) -> str:
    title = (title or '').strip()
    if len(title) > 120:
        title = title[:120]
    return title or 'New conversation'


def validate_draft_body(data: dict) -> tuple[bool, str]:
    """Strict schema check for draft creation payloads."""
    if not isinstance(data, dict):
        return False, 'Expected JSON object'
    draft_type = data.get('type')
    if draft_type not in ('email', 'calendar'):
        return False, 'type must be email or calendar'
    if draft_type == 'email':
        to = data.get('to', '')
        subject = data.get('subject', '')
        body = data.get('body', '')
        if not validate_email(to):
            return False, 'Invalid to address'
        if not subject or len(subject) > 200:
            return False, 'subject missing or too long'
        if not body or len(body) > 10000:
            return False, 'body missing or too long'
    elif draft_type == 'calendar':
        title = data.get('title', '')
        date = data.get('date', '')
        if not title or len(title) > 200:
            return False, 'title missing or too long'
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            return False, 'date must be YYYY-MM-DD'
    return True, ''


def sanitize_page_text(html: str) -> str:
    """Strip tags for plain-text extraction before passing to agent."""
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:50000]