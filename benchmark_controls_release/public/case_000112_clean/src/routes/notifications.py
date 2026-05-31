import logging
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)
notifications_bp = Blueprint('notifications', __name__)


def get_db():
    from flask import current_app
    import sqlite3
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@notifications_bp.route('/notifications')
@login_required
def render_notifications():
    db = get_db()

    # Fetch all notifications for current user, newest first
    notifications = db.execute(
        '''SELECT id, message, is_read, created_at
           FROM notifications
           WHERE user_id = ?
           ORDER BY created_at DESC''',
        (current_user.id,)
    ).fetchall()

    # Mark all as read after viewing
    db.execute(
        'UPDATE notifications SET is_read = 1 WHERE user_id = ?',
        (current_user.id,)
    )
    db.commit()

    logger.info("Rendering notifications for user %d (%d total)",
                current_user.id, len(notifications))

    return render_template('notifications.html', notifications=notifications)


@notifications_bp.route('/notifications/<int:notif_id>/dismiss', methods=['POST'])
@login_required
def dismiss_notification(notif_id):
    db = get_db()
    result = db.execute(
        'DELETE FROM notifications WHERE id = ? AND user_id = ?',
        (notif_id, current_user.id)
    )
    db.commit()
    if result.rowcount == 0:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404
    return jsonify({'status': 'ok'})


@notifications_bp.route('/notifications/clear', methods=['POST'])
@login_required
def clear_all_notifications():
    db = get_db()
    db.execute('DELETE FROM notifications WHERE user_id = ?', (current_user.id,))
    db.commit()
    return redirect(url_for('notifications.render_notifications'))


@notifications_bp.route('/notifications/count')
@login_required
def notification_count():
    db = get_db()
    count = db.execute(
        'SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND is_read = 0',
        (current_user.id,)
    ).fetchone()['c']
    return jsonify({'unread': count})