import logging
from datetime import datetime
from flask import Blueprint, render_template_string, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models.db import get_db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>Admin - TeamHub</title>
<style>
body { font-family: Arial, sans-serif; max-width: 1000px; margin: 40px auto; padding: 20px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background: #f4f4f4; }
.role-admin { color: red; font-weight: bold; }
</style>
</head>
<body>
<h2>Admin Panel</h2>
<h3>Users</h3>
<table>
<tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th><th>Team</th><th>Active</th><th>Actions</th></tr>
{% for u in users %}
<tr>
  <td>{{ u.id }}</td>
  <td><a href="/profile/{{ u.username }}">{{ u.username }}</a></td>
  <td>{{ u.email }}</td>
  <td class="role-{{ u.role }}">{{ u.role }}</td>
  <td>{{ u.team_id }}</td>
  <td>{{ "Yes" if u.is_active else "No" }}</td>
  <td>
    <form method="POST" action="/admin/toggle/{{ u.id }}" style="display:inline">
      <button type="submit">Toggle Active</button>
    </form>
  </td>
</tr>
{% endfor %}
</table>
<h3>Recent Audit Log</h3>
<table>
<tr><th>Time</th><th>User</th><th>Action</th><th>Details</th><th>IP</th></tr>
{% for entry in audit_log %}
<tr>
  <td>{{ entry.created_at }}</td>
  <td>{{ entry.username or 'system' }}</td>
  <td>{{ entry.action }}</td>
  <td>{{ entry.details }}</td>
  <td>{{ entry.ip_address }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
'''


def require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


@admin_bp.route('/')
@login_required
def index():
    require_admin()
    db = get_db()
    try:
        users = db.execute('SELECT * FROM users ORDER BY id').fetchall()
        audit_log = db.execute(
            '''SELECT a.*, u.username FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.created_at DESC LIMIT 50'''
        ).fetchall()
    finally:
        db.close()

    return render_template_string(ADMIN_TEMPLATE, users=users, audit_log=audit_log)


@admin_bp.route('/toggle/<int:user_id>', methods=['POST'])
@login_required
def toggle_user(user_id):
    require_admin()
    db = get_db()
    try:
        user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            abort(404)

        # Prevent admin from deactivating themselves
        if user_id == current_user.id:
            flash('Cannot deactivate your own account.')
            return redirect(url_for('admin.index'))

        new_state = 0 if user['is_active'] else 1
        db.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_state, user_id))
        db.execute(
            'INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, 'admin.toggle', f'User {user["username"]} active={new_state}',
             request.remote_addr, datetime.utcnow().isoformat())
        )
        db.commit()
        logger.info("Admin %s toggled user %s active=%s", current_user.username, user['username'], new_state)
        return redirect(url_for('admin.index'))
    finally:
        db.close()


@admin_bp.route('/audit')
@login_required
def audit():
    require_admin()
    db = get_db()
    try:
        entries = db.execute(
            '''SELECT a.*, u.username FROM audit_log a
               LEFT JOIN users u ON a.user_id = u.id
               ORDER BY a.created_at DESC LIMIT 200'''
        ).fetchall()
    finally:
        db.close()

    return render_template_string('''
    <!DOCTYPE html><html><head><title>Audit Log</title></head><body>
    <h2>Full Audit Log</h2>
    <table border="1">
    <tr><th>Time</th><th>User</th><th>Action</th><th>Details</th><th>IP</th></tr>
    {% for e in entries %}
    <tr><td>{{ e.created_at }}</td><td>{{ e.username }}</td>
        <td>{{ e.action }}</td><td>{{ e.details }}</td><td>{{ e.ip_address }}</td></tr>
    {% endfor %}
    </table></body></html>
    ''', entries=entries)