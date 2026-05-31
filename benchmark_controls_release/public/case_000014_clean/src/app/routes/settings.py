import logging
import hashlib
import os
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify
import middleware
from db import get_db

logger = logging.getLogger('promptforge.settings')
bp = Blueprint('settings', __name__)


@bp.route('/')
@middleware.login_required
def index():
    db = get_db()
    keys = db.execute(
        'SELECT id, label, created_at, last_used FROM api_keys WHERE user_id=? ORDER BY created_at DESC',
        (g.user_id,)
    ).fetchall()
    db.close()
    return render_template('settings.html', api_keys=keys, csrf_token=g.get('csrf_token'))


def _require_csrf():
    return request.form.get('_csrf') == str(g.get('csrf_token', ''))


@bp.route('/api-keys', methods=['POST'])
@middleware.login_required
def create_api_key():
    if not _require_csrf():
        return jsonify({'error': 'csrf token required'}), 403
    label = request.form.get('label', 'default').strip()[:50]
    raw_key = 'pf_' + os.urandom(24).hex()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = get_db()
    db.execute(
        'INSERT INTO api_keys (user_id, key_hash, label) VALUES (?,?,?)',
        (g.user_id, key_hash, label)
    )
    db.commit()
    db.close()
    middleware.audit('api_key_create', f'label={label}')
    return render_template('settings.html',
                           api_keys=_get_keys(),
                           new_key=raw_key,
                           new_key_label=label,
                           csrf_token=g.get('csrf_token'))


@bp.route('/api-keys/<int:kid>', methods=['POST'])
@middleware.login_required
def delete_api_key(kid):
    if not _require_csrf():
        return jsonify({'error': 'csrf token required'}), 403
    db = get_db()
    db.execute('DELETE FROM api_keys WHERE id=? AND user_id=?', (kid, g.user_id))
    db.commit()
    db.close()
    middleware.audit('api_key_delete', f'kid={kid}')
    return redirect(url_for('settings.index'))


@bp.route('/notifications', methods=['POST'])
@middleware.login_required
def update_notifications():
    if not _require_csrf():
        return jsonify({'error': 'csrf token required'}), 403
    # placeholder — would store notification preferences
    middleware.audit('settings_update', 'notification preferences updated')
    return redirect(url_for('settings.index'))


def _get_keys():
    db = get_db()
    keys = db.execute(
        'SELECT id, label, created_at, last_used FROM api_keys WHERE user_id=? ORDER BY created_at DESC',
        (g.user_id,)
    ).fetchall()
    db.close()
    return keys
