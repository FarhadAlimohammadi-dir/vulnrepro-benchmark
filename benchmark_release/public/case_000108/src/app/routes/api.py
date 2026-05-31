from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..models import rotate_api_key, get_user_by_username, log_action, get_all_users

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/v1/keys', methods=['GET'])
@login_required
def list_keys():
    # Only returns caller's own key - no cross-user access
    return jsonify({
        'status': 'ok',
        'keys': [
            {
                'key': current_user.api_key,
                'created_by': current_user.username,
                'type': 'live'
            }
        ]
    })

@api_bp.route('/api/v1/keys/rotate', methods=['POST'])
@login_required
def api_rotate_key():
    new_key = rotate_api_key(current_user.id)
    log_action(current_user.id, 'API_KEY_ROTATE', 'Key rotated via API', request.remote_addr)
    return jsonify({'status': 'ok', 'new_key': new_key})

@api_bp.route('/api/v1/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'display_name': current_user.display_name,
        'role': current_user.role
    })

@api_bp.route('/api/v1/admin/users', methods=['GET'])
@login_required
def admin_list_users():
    # Role check enforced strictly before any data is returned
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    users = get_all_users()
    return jsonify({'users': [dict(u) for u in users]})

@api_bp.route('/api/v1/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'version': '2.1.4'})