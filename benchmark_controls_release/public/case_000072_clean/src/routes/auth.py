import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template_string
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
import db

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>DocuVault — Sign In</title>
<style>
body { font-family: Arial, sans-serif; background: #f5f7fa; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
.card { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); width: 360px; }
h2 { margin-top: 0; color: #2d3748; }
input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #e2e8f0; border-radius: 4px; box-sizing: border-box; }
button { width: 100%; padding: 12px; background: #4299e1; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
.error { color: #e53e3e; margin-top: 8px; }
.brand { color: #4299e1; font-size: 22px; font-weight: bold; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="card">
  <div class="brand">📄 DocuVault</div>
  <h2>Sign In</h2>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="post" action="/auth/login">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Sign In</button>
  </form>
</div>
</body>
</html>
'''


@auth_bp.route('/login', methods=['GET'])
def login_page():
    return render_template_string(LOGIN_TEMPLATE, error=None)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        if request.is_json:
            return jsonify({'error': 'Username and password required.'}), 400
        return render_template_string(LOGIN_TEMPLATE, error='Username and password required.'), 400

    user = User.authenticate(username, password)
    if not user:
        logger.warning(f"Failed login attempt for username='{username}' ip={request.remote_addr}")
        if request.is_json:
            return jsonify({'error': 'Invalid credentials.'}), 401
        return render_template_string(LOGIN_TEMPLATE, error='Invalid credentials.'), 401

    login_user(user, remember=False)
    now = datetime.utcnow().isoformat()
    db.execute('UPDATE users SET last_login=? WHERE id=?', (now, user.id))
    db.execute(
        'INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, created_at) VALUES (?,?,?,?,?,?,?)',
        (user.id, 'user.login', 'user', user.id, '{}', request.remote_addr, now)
    )

    logger.info(f"User '{username}' logged in from {request.remote_addr}")
    if request.is_json:
        return jsonify({'message': 'Logged in.', 'user': {'id': user.id, 'username': user.username, 'role': user.role}})
    from flask import redirect, url_for
    return redirect('/api/documents/list')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f"User '{username}' logged out.")
    return jsonify({'message': 'Logged out.'})


@auth_bp.route('/register', methods=['POST'])
def register():
    """Self-service registration for new accounts."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required.'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'username, email, and password are required.'}), 400

    if len(username) < 3 or len(username) > 32:
        return jsonify({'error': 'Username must be 3-32 characters.'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400

    existing = db.query_one('SELECT id FROM users WHERE username=? OR email=?', (username, email))
    if existing:
        return jsonify({'error': 'Username or email already in use.'}), 409

    try:
        user = User.create(username, email, password)
        logger.info(f"New user registered: '{username}'")
        return jsonify({'message': 'Account created.', 'user_id': user.id}), 201
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed.'}), 500


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role,
    })