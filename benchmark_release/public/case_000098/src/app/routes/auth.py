import bcrypt
import logging
from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from app.models import get_db
from app import login_manager

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

    def is_admin(self):
        return self.role == 'admin'

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    db.close()
    if row:
        return User(row['id'], row['username'], row['email'], row['role'])
    return None

@auth_bp.route('/')
def index():
    return jsonify({
        "service": "WebHook Relay Service",
        "version": "2.4.1",
        "docs": "/api/docs",
        "status": "operational"
    })

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
    ).fetchone()
    db.close()

    if not row:
        logger.warning("Login attempt for unknown user: %s", username)
        return jsonify({"error": "Invalid credentials"}), 401

    if not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        logger.warning("Failed login for user: %s", username)
        return jsonify({"error": "Invalid credentials"}), 401

    user = User(row['id'], row['username'], row['email'], row['role'])
    login_user(user)
    logger.info("User logged in: %s", username)

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info("User logged out: %s", username)
    return jsonify({"success": True})

@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role
    })

@auth_bp.route('/api/admin/events', methods=['GET'])
@login_required
def admin_events():
    if not current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()
    rows = db.execute(
        '''SELECT ae.*, u.username FROM audit_events ae
           LEFT JOIN users u ON ae.user_id = u.id
           ORDER BY ae.created_at DESC LIMIT 100'''
    ).fetchall()
    db.close()

    events = []
    for r in rows:
        events.append({
            "id": r['id'],
            "username": r['username'],
            "action": r['action'],
            "resource_type": r['resource_type'],
            "resource_id": r['resource_id'],
            "details": r['details'],
            "ip_address": r['ip_address'],
            "created_at": r['created_at']
        })

    return jsonify({"events": events, "count": len(events)})