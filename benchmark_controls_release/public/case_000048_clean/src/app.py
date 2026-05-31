import os
import logging
import bcrypt
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from models.database import init_db, get_db, get_user_by_username, write_audit
from routes.api import api_bp
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'flowci-dev-secret-2023')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/app/data/flowci.db')

    # Ensure data and config directories exist
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)
    os.makedirs(os.environ.get('CONFIG_DIR', '/app/config'), exist_ok=True)

    # Initialize DB
    init_db()

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    def dashboard():
        conn = get_db()
        try:
            projects = conn.execute('SELECT COUNT(*) as c FROM projects').fetchone()['c']
            builds = conn.execute('SELECT COUNT(*) as c FROM builds').fetchone()['c']
            users = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
            recent_builds = conn.execute(
                '''SELECT b.id, b.status, b.branch, b.started_at, p.name as project_name, u.username
                   FROM builds b
                   JOIN projects p ON b.project_id = p.id
                   JOIN users u ON b.triggered_by = u.id
                   ORDER BY b.id DESC LIMIT 10'''
            ).fetchall()
        finally:
            conn.close()

        return render_template(
            'dashboard.html',
            projects=projects,
            builds=builds,
            users=users,
            recent_builds=[dict(r) for r in recent_builds]
        )

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            data = request.get_json() or request.form
            username = data.get('username', '')
            password = data.get('password', '')

            user = get_user_by_username(username)
            if not user:
                return jsonify({'error': 'Invalid credentials'}), 401

            if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                return jsonify({'error': 'Invalid credentials'}), 401

            if not user['is_active']:
                return jsonify({'error': 'Account disabled'}), 403

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            # Update last login
            conn = get_db()
            try:
                conn.execute(
                    'UPDATE users SET last_login = ? WHERE id = ?',
                    (datetime.now(timezone.utc).isoformat(), user['id'])
                )
                conn.commit()
            finally:
                conn.close()

            write_audit(user['id'], 'user_login', f"user:{user['id']}", request.remote_addr, 'Successful login')
            return jsonify({'message': 'Login successful', 'role': user['role']}), 200

        return render_template('login.html')

    @app.route('/logout', methods=['POST'])
    def logout():
        user_id = session.get('user_id')
        session.clear()
        if user_id:
            write_audit(user_id, 'user_logout', f'user:{user_id}', request.remote_addr)
        return jsonify({'message': 'Logged out'}), 200

    @app.route('/status')
    def status():
        """Public health-check endpoint."""
        return jsonify({
            'status': 'ok',
            'service': 'FlowCI',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal server error: %s", e)
        return jsonify({'error': 'Internal server error'}), 500

    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    app = create_app()
    logger.info("Starting FlowCI on port %d", port)
    app.run(host='0.0.0.0', port=port, debug=False)