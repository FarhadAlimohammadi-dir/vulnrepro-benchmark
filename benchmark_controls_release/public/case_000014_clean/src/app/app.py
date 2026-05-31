import os
import secrets
import logging
from flask import Flask, request, jsonify, session, redirect, url_for, render_template, g
from db import get_db, init_db
import middleware
import routes.auth as auth_bp
import routes.prompts as prompts_bp
import routes.admin as admin_bp
import routes.settings as settings_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger('promptforge')

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Register blueprints
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(prompts_bp.bp, url_prefix='/api/prompts')
    app.register_blueprint(admin_bp.bp, url_prefix='/admin')
    app.register_blueprint(settings_bp.bp, url_prefix='/settings')

    @app.before_request
    def load_user():
        g.user_id = session.get('user_id')
        g.username = session.get('username')
        g.role = session.get('role', 'user')
        if g.user_id and not session.get('csrf_token'):
            session['csrf_token'] = secrets.token_urlsafe(32)
        g.csrf_token = session.get('csrf_token')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '2.1.0'})

    @app.route('/')
    def index():
        if g.user_id:
            return redirect(url_for('dashboard'))
        return render_template('index.html')

    @app.route('/dashboard')
    @middleware.login_required
    def dashboard():
        db = get_db()
        prompts = db.execute(
            '''SELECT id, name, model, prompt_type, created_at
               FROM prompts WHERE user_id=?
               ORDER BY created_at DESC LIMIT 10''',
            (g.user_id,)
        ).fetchall()
        stats = db.execute(
            'SELECT COUNT(*) as cnt FROM prompts WHERE user_id=?',
            (g.user_id,)
        ).fetchone()
        recent_logs = db.execute(
            '''SELECT action, detail, created_at FROM audit_log
               WHERE user_id=? ORDER BY created_at DESC LIMIT 5''',
            (g.user_id,)
        ).fetchall()
        return render_template(
            'dashboard.html',
            prompts=prompts,
            total_prompts=stats['cnt'],
            recent_logs=recent_logs,
        )

    @app.route('/prompts')
    @middleware.login_required
    def prompt_library():
        db = get_db()
        page = max(1, int(request.args.get('page', 1)))
        per_page = 12
        offset = (page - 1) * per_page
        search = request.args.get('q', '').strip()
        if search:
            rows = db.execute(
                '''SELECT id, name, model, prompt_type, created_at
                   FROM prompts WHERE user_id=? AND name LIKE ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                (g.user_id, '%' + search + '%', per_page, offset)
            ).fetchall()
            total = db.execute(
                'SELECT COUNT(*) as cnt FROM prompts WHERE user_id=? AND name LIKE ?',
                (g.user_id, '%' + search + '%')
            ).fetchone()['cnt']
        else:
            rows = db.execute(
                '''SELECT id, name, model, prompt_type, created_at
                   FROM prompts WHERE user_id=?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                (g.user_id, per_page, offset)
            ).fetchall()
            total = db.execute(
                'SELECT COUNT(*) as cnt FROM prompts WHERE user_id=?',
                (g.user_id,)
            ).fetchone()['cnt']
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template(
            'prompt_library.html',
            prompts=rows,
            page=page,
            total_pages=total_pages,
            search=search,
            total=total,
        )

    @app.route('/prompts/<int:pid>')
    @middleware.login_required
    def prompt_detail(pid):
        db = get_db()
        row = db.execute(
            'SELECT * FROM prompts WHERE id=? AND user_id=?',
            (pid, g.user_id)
        ).fetchone()
        if not row:
            return render_template('error.html', code=404, message='Prompt not found'), 404
        import json
        body = {}
        try:
            body = json.loads(row['body'])
        except Exception:
            pass
        return render_template('prompt_detail.html', prompt=row, body=body)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, message='Page not found'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error('Internal error: %s', e)
        return render_template('error.html', code=500, message='Internal server error'), 500

    return app


app = create_app()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 9000))
    logger.info('Starting PromptForge on port %d', port)
    app.run(host='0.0.0.0', port=port, debug=False)
