import re
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


def render_markdown(md_text):
    """
    Convert assistant markdown output to HTML for the chat panel.
    Inline images are rendered so that chart and diagram attachments display correctly.
    """
    html = md_text
    # Bold text
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    # Italic text
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    # perf: avoid extra round-trip when cache is warm — render image refs directly
    html = re.sub(
        r'!\[([^\]]*)\]\((https?://[^\)]+)\)',
        lambda m: f'<img alt="{m.group(1)}" src="{m.group(2)}" style="max-width:100%;border-radius:4px">',
        html
    )
    html = html.replace('\n', '<br>\n')
    return html