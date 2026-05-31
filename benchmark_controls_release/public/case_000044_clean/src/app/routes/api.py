import logging
import bcrypt
from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from ..database import get_db
from ..models import User, Project

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


def log_action(user_id, action, resource_type=None, resource_id=None, details=None):
    """Write an entry to the audit log for compliance tracking."""
    conn = get_db()
    ip = request.remote_addr or '0.0.0.0'
    conn.execute(
        "INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES (?,?,?,?,?,?)",
        (user_id, action, resource_type, resource_id, details, ip)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/auth/login', methods=['POST'])
def login():
    """Authenticate a user and establish a session."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.get_by_username(username)
    if not user or not user.check_password(password):
        logger.warning("Failed login attempt for username: %s", username)
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.active:
        return jsonify({'error': 'Account is disabled'}), 403

    login_user(user)
    log_action(user.id, 'user.login', 'user', user.id, 'Successful login')

    conn = get_db()
    conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user.id,))
    conn.commit()
    conn.close()

    logger.info("User %s logged in", username)
    return jsonify({'message': 'Login successful', 'user': user.to_dict()}), 200


@api_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """End the current user session."""
    log_action(current_user.id, 'user.logout')
    logout_user()
    return jsonify({'message': 'Logged out'}), 200


# ---------------------------------------------------------------------------
# User registration — processes incoming fields for new account creation
# ---------------------------------------------------------------------------

@api_bp.route('/users/register', methods=['POST'])
def register_user():
    """
    Create a new ProjectHub account.

    Accepts a JSON body with account details and persists the new user
    record. All provided fields are forwarded to the persistence layer so
    that future API expansions (e.g. SSO pre-provisioning) work without
    a code change.

    # legacy: kept for v1 API clients still in the wild
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['username', 'email', 'password']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    if User.get_by_username(username):
        return jsonify({'error': 'Username already taken'}), 409
    if User.get_by_email(email):
        return jsonify({'error': 'Email already registered'}), 409

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    allowed_columns = {'username', 'email', 'full_name', 'department'}
    user_fields = {k: v for k, v in data.items() if k in allowed_columns and k != 'password'}
    user_fields['password_hash'] = pw_hash
    user_fields['role'] = 'user'

    columns = ', '.join(user_fields.keys())
    placeholders = ', '.join(['?' for _ in user_fields])
    values = list(user_fields.values())

    conn = get_db()
    try:
        cur = conn.execute(
            f"INSERT INTO users ({columns}) VALUES ({placeholders})",
            values
        )
        new_id = cur.lastrowid
        conn.commit()
    except Exception as e:
        conn.close()
        logger.error("Registration error: %s", str(e))
        return jsonify({'error': 'Registration failed'}), 500

    conn.close()

    new_user = User.get_by_id(new_id)
    log_action(new_id, 'user.register', 'user', new_id, f'New account: {username}')
    logger.info("New user registered: %s (role=%s)", username, new_user.role)

    return jsonify({'message': 'Account created', 'user': new_user.to_dict()}), 201


# ---------------------------------------------------------------------------
# User profile endpoints (safe — explicit field whitelist)
# ---------------------------------------------------------------------------

@api_bp.route('/users/<int:user_id>/profile', methods=['GET'])
@login_required
def get_profile(user_id):
    """Return public profile data for a user."""
    if current_user.id != user_id and not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403

    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'user': user.to_dict()}), 200


@api_bp.route('/users/<int:user_id>/settings', methods=['PUT'])
@login_required
def update_settings(user_id):
    """
    Update non-sensitive account preferences.

    Only full_name and department may be changed through this endpoint.
    Role and permission changes go through the admin console.
    """
    if current_user.id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}

    # Explicit field whitelist — only cosmetic profile fields
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    full_name = data.get('full_name', user.full_name)
    department = data.get('department', user.department)

    conn = get_db()
    conn.execute(
        "UPDATE users SET full_name = ?, department = ? WHERE id = ?",
        (full_name, department, user_id)
    )
    conn.commit()
    conn.close()

    log_action(current_user.id, 'user.settings_update', 'user', user_id, 'Updated profile settings')
    return jsonify({'message': 'Settings updated'}), 200


@api_bp.route('/users/<int:user_id>/password', methods=['PUT'])
@login_required
def change_password(user_id):
    """
    Change account password after verifying the current credential.

    Admins may reset passwords without providing the old credential.
    """
    if current_user.id != user_id and not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    new_password = data.get('new_password', '')

    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if not current_user.is_admin():
        current_password = data.get('current_password', '')
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401

    pw_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
    conn.commit()
    conn.close()

    log_action(current_user.id, 'user.password_change', 'user', user_id, 'Password changed')
    return jsonify({'message': 'Password updated'}), 200


# ---------------------------------------------------------------------------
# Admin endpoints — role-gated
# ---------------------------------------------------------------------------

@api_bp.route('/admin/users', methods=['GET'])
@login_required
def list_all_users():
    """List all registered users. Admin access required."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    users = User.get_all()
    return jsonify({'users': [u.to_dict() for u in users]}), 200


@api_bp.route('/admin/users/<int:user_id>/role', methods=['PUT'])
@login_required
def update_user_role(user_id):
    """
    Promote or demote a user's role. Admin access required.

    This is the only legitimate path for role changes — it requires
    an already-authenticated admin session before accepting the new value.
    """
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    new_role = data.get('role', '')

    if new_role not in ('user', 'admin', 'moderator'):
        return jsonify({'error': 'Invalid role value'}), 400

    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    conn = get_db()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

    log_action(current_user.id, 'admin.role_update', 'user', user_id,
               f'Role changed to {new_role}')
    return jsonify({'message': 'Role updated', 'user_id': user_id, 'new_role': new_role}), 200


@api_bp.route('/admin/audit-logs', methods=['GET'])
@login_required
def get_audit_logs():
    """Return recent audit log entries. Admin access required."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    limit = min(int(request.args.get('limit', 50)), 200)
    conn = get_db()
    rows = conn.execute(
        "SELECT al.*, u.username FROM audit_logs al "
        "LEFT JOIN users u ON al.user_id = u.id "
        "ORDER BY al.created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()

    return jsonify({'logs': [dict(r) for r in rows]}), 200


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@api_bp.route('/projects', methods=['GET'])
@login_required
def list_projects():
    """Return projects visible to the current user."""
    if current_user.is_admin():
        projects = Project.get_all()
    else:
        projects = Project.get_by_owner(current_user.id)

    return jsonify({'projects': [p.to_dict() for p in projects]}), 200


@api_bp.route('/projects', methods=['POST'])
@login_required
def create_project():
    """Create a new project owned by the current user."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    description = data.get('description', '')

    if not name:
        return jsonify({'error': 'Project name is required'}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
        (name, description, current_user.id)
    )
    project_id = cur.lastrowid
    conn.commit()
    conn.close()

    log_action(current_user.id, 'project.create', 'project', project_id,
               f'Created project: {name}')
    return jsonify({'message': 'Project created', 'project_id': project_id}), 201


@api_bp.route('/search', methods=['POST'])
@login_required
def search():
    """
    Search projects and tasks by keyword.
    Uses parameterized queries throughout.
    """
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()

    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    pattern = f'%{query}%'
    conn = get_db()

    if current_user.is_admin():
        projects = conn.execute(
            "SELECT id, name, description FROM projects WHERE name LIKE ? OR description LIKE ?",
            (pattern, pattern)
        ).fetchall()

        tasks = conn.execute(
            "SELECT id, title, status FROM tasks WHERE title LIKE ? OR description LIKE ?",
            (pattern, pattern)
        ).fetchall()
    else:
        projects = conn.execute(
            """
            SELECT DISTINCT p.id, p.name, p.description
              FROM projects p
              LEFT JOIN memberships m ON m.project_id = p.id
             WHERE (p.name LIKE ? OR p.description LIKE ?)
               AND (p.owner_id = ? OR m.user_id = ?)
            """,
            (pattern, pattern, current_user.id, current_user.id)
        ).fetchall()

        tasks = conn.execute(
            """
            SELECT DISTINCT t.id, t.title, t.status
              FROM tasks t
              JOIN projects p ON p.id = t.project_id
              LEFT JOIN memberships m ON m.project_id = p.id
             WHERE (t.title LIKE ? OR t.description LIKE ?)
               AND (p.owner_id = ? OR m.user_id = ?)
            """,
            (pattern, pattern, current_user.id, current_user.id)
        ).fetchall()

    conn.close()

    return jsonify({
        'projects': [dict(r) for r in projects],
        'tasks': [dict(r) for r in tasks],
    }), 200
