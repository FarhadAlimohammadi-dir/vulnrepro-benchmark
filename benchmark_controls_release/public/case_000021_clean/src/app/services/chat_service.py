import re
import html as html_lib
from app.db import get_connection


class ChatService:

    @staticmethod
    def save_message(user_id, user_message, ai_response, doc_count=0):
        conn = get_connection()
        try:
            conn.execute(
                'INSERT INTO chat_history (user_id, user_message, ai_response, doc_count) VALUES (?, ?, ?, ?)',
                (user_id, user_message, ai_response, doc_count)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_history(user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT id, user_message, ai_response, doc_count, created_at FROM chat_history '
                'WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def clear_history(user_id):
        conn = get_connection()
        try:
            conn.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def export_history(user_id, username):
        conn = get_connection()
        try:
            rows = conn.execute(
                'SELECT user_message, ai_response, created_at FROM chat_history '
                'WHERE user_id = ? ORDER BY created_at ASC',
                (user_id,)
            ).fetchall()
            lines = [f'DocuMind Export – {username}', '=' * 48]
            for row in rows:
                msg = row['user_message'].replace('<', '&lt;').replace('>', '&gt;')
                resp = row['ai_response'].replace('<', '&lt;').replace('>', '&gt;')
                lines.append(f'\nUser [{row["created_at"]}]: {msg}')
                lines.append(f'AI: {resp}')
            return '\n'.join(lines)
        finally:
            conn.close()


_MD_IMAGE_URL_RE = re.compile(r'!\[([^\]]*)\]\((https?://[^\s\)\'"<>]+)\)')


def _safe_image_link(label, url):
    # Reject URLs containing characters that could allow attribute injection
    # after HTML entity decoding by the browser.
    if any(c in url for c in ('"', "'", '<', '>', '`', '\\', '\x00')):
        return ''
    # Only http/https schemes are permitted.
    if not (url.startswith('http://') or url.startswith('https://')):
        return ''
    escaped_url = html_lib.escape(url, quote=True)
    escaped_label = html_lib.escape(label or '', quote=True)
    return f'<a href="{escaped_url}">{escaped_label}</a>'


def render_markdown(md_text):
    """
    Convert assistant markdown output to HTML for the chat panel.
    Inline images are rendered so that chart and diagram attachments display correctly.

    Image/link URLs are parsed from the raw markdown BEFORE HTML escaping and
    then re-emitted with a properly quoted, fully escaped href. This avoids
    the previous shape where a regex over already-escaped text could pick up
    entities such as &#34; inside the captured URL and allow attribute
    breakout when the browser decoded them.
    """
    src = md_text or ''

    placeholders = []

    def _stash(match):
        token = f'\x00IMG{len(placeholders)}\x00'
        placeholders.append(_safe_image_link(match.group(1), match.group(2)))
        return token

    src = _MD_IMAGE_URL_RE.sub(_stash, src)

    html = html_lib.escape(src, quote=True)
    # Bold text
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    # Italic text
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    for idx, replacement in enumerate(placeholders):
        html = html.replace(f'\x00IMG{idx}\x00', replacement)

    html = html.replace('\n', '<br>\n')
    return html
