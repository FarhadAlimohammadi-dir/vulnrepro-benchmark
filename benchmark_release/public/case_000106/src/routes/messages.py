import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models.db import get_db

logger = logging.getLogger(__name__)
messages_bp = Blueprint('messages', __name__, url_prefix='/messages')

INBOX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>Inbox - TeamHub</title>
<style>
body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
.msg { border-bottom: 1px solid #eee; padding: 10px 0; }
.unread { font-weight: bold; }
a { color: #0066cc; }
</style>
</head>
<body>
<h2>Inbox</h2>
<a href="/messages/compose">Compose</a>
{% for msg in messages %}
<div class="msg {% if not msg.read %}unread{% endif %}">
  <strong>From:</strong> {{ msg.sender_name }}<br>
  <strong>Subject:</strong> <a href="/messages/{{ msg.id }}">{{ msg.subject }}</a><br>
  <strong>Date:</strong> {{ msg.created_at }}
</div>
{% else %}
<p>No messages.</p>
{% endfor %}
</body>
</html>
'''


@messages_bp.route('/')
@login_required
def inbox():
    db = get_db()
    try:
        msgs = db.execute(
            '''SELECT m.*, u.display_name as sender_name
               FROM messages m JOIN users u ON m.sender_id = u.id
               WHERE m.recipient_id = ? ORDER BY m.created_at DESC''',
            (current_user.id,)
        ).fetchall()
    finally:
        db.close()
    return render_template_string(INBOX_TEMPLATE, messages=msgs)


@messages_bp.route('/<int:msg_id>')
@login_required
def view_message(msg_id):
    db = get_db()
    try:
        msg = db.execute(
            '''SELECT m.*, u.display_name as sender_name, u.username as sender_username
               FROM messages m JOIN users u ON m.sender_id = u.id
               WHERE m.id = ? AND m.recipient_id = ?''',
            (msg_id, current_user.id)
        ).fetchone()
        if not msg:
            abort(404)
        db.execute('UPDATE messages SET read = 1 WHERE id = ?', (msg_id,))
        db.commit()
    finally:
        db.close()

    return render_template_string('''
    <!DOCTYPE html><html><head><title>Message - TeamHub</title></head><body>
    <h3>{{ msg.subject }}</h3>
    <p><strong>From:</strong> <a href="/profile/{{ msg.sender_username }}">{{ msg.sender_name }}</a></p>
    <p><strong>Date:</strong> {{ msg.created_at }}</p>
    <hr>
    <p>{{ msg.body }}</p>
    <a href="/messages/">Back to inbox</a>
    </body></html>
    ''', msg=msg)


@messages_bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    if request.method == 'POST':
        to_username = request.form.get('to', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not all([to_username, subject, body]):
            flash('All fields required.')
            return redirect(url_for('messages.compose'))

        db = get_db()
        try:
            recipient = db.execute(
                'SELECT id FROM users WHERE username = ? AND is_active = 1', (to_username,)
            ).fetchone()
            if not recipient:
                flash('User not found.')
                return redirect(url_for('messages.compose'))

            db.execute(
                'INSERT INTO messages (sender_id, recipient_id, subject, body, created_at) VALUES (?, ?, ?, ?, ?)',
                (current_user.id, recipient['id'], subject, body, datetime.utcnow().isoformat())
            )
            db.commit()
            flash('Message sent.')
            return redirect(url_for('messages.inbox'))
        finally:
            db.close()

    return render_template_string('''
    <!DOCTYPE html><html><head><title>Compose - TeamHub</title></head><body>
    <h2>Compose Message</h2>
    {% for msg in get_flashed_messages() %}<p style="color:red">{{ msg }}</p>{% endfor %}
    <form method="POST">
      <input type="text" name="to" placeholder="Username" required><br>
      <input type="text" name="subject" placeholder="Subject" required><br>
      <textarea name="body" placeholder="Message" rows="6" required></textarea><br>
      <button type="submit">Send</button>
    </form>
    </body></html>
    ''')