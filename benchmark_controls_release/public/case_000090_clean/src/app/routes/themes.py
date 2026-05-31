import os
import sys
import uuid
import zipfile
import json
import tempfile
import shutil
import logging
import importlib.util
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import get_db

themes_bp = Blueprint('themes', __name__, url_prefix='/api/themes')
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'zip', 'hwt'}
ALLOWED_CATEGORIES = {'dark', 'light', 'nature', 'retro', 'minimal', 'earth', 'general'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _record_audit(db, user_id, action, target_type, target_id, details, ip):
    db.execute(
        "INSERT INTO audit_log (user_id, action, target_type, target_id, details, ip_address) VALUES (?,?,?,?,?,?)",
        (user_id, action, target_type, target_id, details, ip)
    )


@themes_bp.route('', methods=['GET'])
def list_themes():
    """Return paginated list of approved themes with optional filtering."""
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(1, int(request.args.get('per_page', 20))))
    category = request.args.get('category', '')
    sort_by = request.args.get('sort_by', 'created_at')

    valid_sorts = {'created_at', 'downloads', 'name', 'rating_sum'}
    if sort_by not in valid_sorts:
        sort_by = 'created_at'

    offset = (page - 1) * per_page
    db = get_db()

    query = "SELECT t.*, u.username as author_name FROM themes t JOIN users u ON t.author_id = u.id WHERE t.status = 'approved'"
    params = []

    if category and category in ALLOWED_CATEGORIES:
        query += " AND t.category = ?"
        params.append(category)

    query += f" ORDER BY t.{sort_by} DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    rows = db.execute(query, params).fetchall()
    themes = []
    for r in rows:
        themes.append({
            'id': r['id'],
            'name': r['name'],
            'description': r['description'],
            'author': r['author_name'],
            'category': r['category'],
            'tags': r['tags'],
            'downloads': r['downloads'],
            'rating': round(r['rating_sum'] / r['rating_count'], 1) if r['rating_count'] > 0 else 0,
            'engine_version': r['engine_version'],
            'created_at': r['created_at'],
        })

    return jsonify({'themes': themes, 'page': page, 'per_page': per_page}), 200


@themes_bp.route('/<int:theme_id>', methods=['GET'])
def get_theme(theme_id):
    """Fetch a single theme by ID."""
    db = get_db()
    row = db.execute(
        "SELECT t.*, u.username as author_name FROM themes t JOIN users u ON t.author_id = u.id WHERE t.id = ?",
        (theme_id,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Theme not found'}), 404

    return jsonify({
        'id': row['id'],
        'name': row['name'],
        'description': row['description'],
        'author': row['author_name'],
        'category': row['category'],
        'tags': row['tags'],
        'downloads': row['downloads'],
        'rating': round(row['rating_sum'] / row['rating_count'], 1) if row['rating_count'] > 0 else 0,
        'engine_version': row['engine_version'],
        'status': row['status'],
        'created_at': row['created_at'],
    }), 200


@themes_bp.route('/upload', methods=['POST'])
@login_required
def upload_theme():
    """Accept a theme archive upload and register it in the marketplace."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f.filename or not allowed_file(f.filename):
        return jsonify({'error': 'Only .zip and .hwt files are accepted'}), 400

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', 'general').strip()

    if not name or len(name) > 100:
        return jsonify({'error': 'Theme name required (max 100 chars)'}), 400

    if category not in ALLOWED_CATEGORIES:
        category = 'general'

    # Validate the archive has at least a manifest
    try:
        with zipfile.ZipFile(f.stream, 'r') as zf:
            names_in_zip = zf.namelist()
            if 'theme.json' not in names_in_zip:
                return jsonify({'error': 'Archive must contain theme.json manifest'}), 400
            manifest_data = json.loads(zf.read('theme.json'))
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        return jsonify({'error': f'Invalid archive or manifest: {str(e)}'}), 400

    engine_version = str(manifest_data.get('engine_version', '1.0'))

    # Reset stream and save
    f.stream.seek(0)
    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
    save_path = os.path.join(upload_dir, stored_name)
    f.save(save_path)

    db = get_db()
    cur = db.execute(
        """INSERT INTO themes (name, description, author_id, category, filename, engine_version, status)
           VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
        (name, description, current_user.id, category, stored_name, engine_version)
    )
    theme_id = cur.lastrowid

    _record_audit(db, current_user.id, 'upload_theme', 'theme', theme_id,
                  f'Uploaded theme: {name}', request.remote_addr)
    db.commit()

    logger.info("User %s uploaded theme '%s' (id=%d)", current_user.username, name, theme_id)
    return jsonify({'message': 'Theme uploaded successfully', 'theme_id': theme_id, 'status': 'pending'}), 201


@themes_bp.route('/<int:theme_id>/activate', methods=['POST'])
@login_required
def activate_theme(theme_id):
    """
    Activate a theme for the current user's session.

    Themes using engine_version 2.0 support extension plugins defined in
    theme.json under the 'extension_plugin' key. The plugin is a Python
    module bundled inside the theme archive that provides a get_preview()
    callable for rendering live previews.

    legacy: kept for v1 API clients still in the wild
    """
    db = get_db()
    row = db.execute(
        "SELECT * FROM themes WHERE id = ? AND status = 'approved'",
        (theme_id,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Theme not found or not approved'}), 404

    upload_dir = current_app.config['UPLOAD_FOLDER']
    theme_path = os.path.join(upload_dir, row['filename'])

    if not os.path.exists(theme_path):
        return jsonify({'error': 'Theme archive not found on server'}), 500

    preview_output = None
    extract_dir = None

    try:
        extract_dir = tempfile.mkdtemp(prefix='theme_preview_')
        extract_root = os.path.realpath(extract_dir)
        with zipfile.ZipFile(theme_path, 'r') as zf:
            # Safe extraction: validate each member path resolves inside
            # extract_root, and reject absolute, drive-qualified, or
            # symlink entries to prevent zip-slip path traversal.
            for member in zf.infolist():
                member_name = member.filename
                if not member_name or member_name.endswith('/'):
                    # Directory entries get created implicitly by file writes.
                    if member_name and (
                        member_name.startswith('/') or
                        member_name.startswith('\\') or
                        '..' in member_name.replace('\\', '/').split('/')
                    ):
                        raise ValueError(f'Unsafe directory entry in archive: {member_name!r}')
                    continue
                normalised = member_name.replace('\\', '/')
                if normalised.startswith('/') or (len(normalised) > 1 and normalised[1] == ':'):
                    raise ValueError(f'Absolute path not permitted in archive: {member_name!r}')
                if '..' in normalised.split('/'):
                    raise ValueError(f'Path traversal not permitted in archive: {member_name!r}')
                # External attribute 0xA1ED0000 marks symlinks on Unix zips.
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f'Symlink entries are not permitted: {member_name!r}')
                dest_path = os.path.realpath(os.path.join(extract_root, normalised))
                if os.path.commonpath([dest_path, extract_root]) != extract_root:
                    raise ValueError(f'Archive entry escapes extraction directory: {member_name!r}')
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member, 'r') as src, open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

        manifest_path = os.path.join(extract_dir, 'theme.json')
        with open(manifest_path, 'r') as mf:
            manifest = json.load(mf)

        # perf: avoid extra round-trip when cache is warm
        engine_ver = manifest.get('engine_version', '1.0')

        if engine_ver == '2.0' and 'extension_plugin' in manifest:
            preview_output = "Extension previews are disabled for uploaded themes"

    except Exception as e:
        logger.error("Error loading theme extension for theme %d: %s", theme_id, str(e))
        return jsonify({'error': 'Failed to load theme extension'}), 500
    finally:
        if extract_dir and os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)

    # Update activation record
    db.execute(
        "INSERT INTO activations (theme_id, user_id) VALUES (?, ?)",
        (theme_id, current_user.id)
    )
    db.execute(
        "UPDATE themes SET downloads = downloads + 1 WHERE id = ?",
        (theme_id,)
    )
    _record_audit(db, current_user.id, 'activate_theme', 'theme', theme_id,
                  f'Activated theme id={theme_id}', request.remote_addr)
    db.commit()

    response = {
        'message': 'Theme activated successfully',
        'theme_id': theme_id,
        'name': row['name'],
    }
    if preview_output is not None:
        response['preview'] = preview_output

    return jsonify(response), 200


@themes_bp.route('/<int:theme_id>/rate', methods=['POST'])
@login_required
def rate_theme(theme_id):
    """Submit or update a star rating and optional review for a theme."""
    data = request.get_json(silent=True) or {}
    score = data.get('score')
    review = data.get('review', '').strip()

    if score is None or not isinstance(score, int) or score < 1 or score > 5:
        return jsonify({'error': 'Score must be an integer between 1 and 5'}), 400

    if len(review) > 1000:
        return jsonify({'error': 'Review must be under 1000 characters'}), 400

    db = get_db()
    theme = db.execute("SELECT * FROM themes WHERE id = ? AND status = 'approved'", (theme_id,)).fetchone()
    if not theme:
        return jsonify({'error': 'Theme not found'}), 404

    existing = db.execute(
        "SELECT * FROM ratings WHERE theme_id = ? AND user_id = ?",
        (theme_id, current_user.id)
    ).fetchone()

    if existing:
        old_score = existing['score']
        db.execute(
            "UPDATE ratings SET score = ?, review = ? WHERE theme_id = ? AND user_id = ?",
            (score, review, theme_id, current_user.id)
        )
        db.execute(
            "UPDATE themes SET rating_sum = rating_sum - ? + ? WHERE id = ?",
            (old_score, score, theme_id)
        )
    else:
        db.execute(
            "INSERT INTO ratings (theme_id, user_id, score, review) VALUES (?, ?, ?, ?)",
            (theme_id, current_user.id, score, review)
        )
        db.execute(
            "UPDATE themes SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 WHERE id = ?",
            (score, theme_id)
        )

    _record_audit(db, current_user.id, 'rate_theme', 'theme', theme_id,
                  f'Rated theme {theme_id} with score {score}', request.remote_addr)
    db.commit()

    return jsonify({'message': 'Rating submitted', 'score': score}), 200


@themes_bp.route('/<int:theme_id>/approve', methods=['POST'])
@login_required
def approve_theme(theme_id):
    """Admin-only: approve or reject a pending theme submission."""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json(silent=True) or {}
    action = data.get('action', 'approve')

    if action not in ('approve', 'reject'):
        return jsonify({'error': 'Action must be approve or reject'}), 400

    new_status = 'approved' if action == 'approve' else 'rejected'

    db = get_db()
    theme = db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
    if not theme:
        return jsonify({'error': 'Theme not found'}), 404

    db.execute("UPDATE themes SET status = ? WHERE id = ?", (new_status, theme_id))
    _record_audit(db, current_user.id, f'{action}_theme', 'theme', theme_id,
                  f'Admin {action}d theme id={theme_id}', request.remote_addr)
    db.commit()

    logger.info("Admin %s %sd theme %d", current_user.username, action, theme_id)
    return jsonify({'message': f'Theme {action}d', 'status': new_status}), 200
