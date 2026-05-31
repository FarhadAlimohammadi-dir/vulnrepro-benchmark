"""
REST API routes — model and dataset upload, config retrieval.
"""
import json
import os
import zipfile

from flask import Blueprint, request, session, jsonify

from db import get_db
from middleware.auth import api_login_required
from services.model_service import (
    sanitize_name, create_model_record, get_user_models,
    get_model_by_id, can_view_model, delete_model, increment_download, set_tags,
)
from services.archive_service import fast_preview, full_preview
from services.audit_service import log_action

bp = Blueprint('api', __name__, url_prefix='/api')

UPLOAD_DIR = '/tmp/modelhub_uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

_ALLOWED_KERAS   = {'keras'}
_ALLOWED_DATA    = {'csv', 'json', 'jsonl'}
_ALLOWED_WEIGHTS = {'h5', 'hdf5'}


def _ext(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


# ── Dataset upload ────────────────────────────────────────────────────────────

@bp.route('/upload/dataset', methods=['POST'])
@api_login_required
def upload_dataset():
    """Accept CSV or JSON dataset files; store and count rows."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    f = request.files['file']
    if _ext(f.filename) not in _ALLOWED_DATA:
        return jsonify({'error': 'Only csv / json / jsonl accepted'}), 415

    safe_fname = f'ds_{session["user_id"]}_{os.path.basename(f.filename)}'
    dest = os.path.join(UPLOAD_DIR, safe_fname)
    f.save(dest)

    try:
        with open(dest, 'r', errors='replace') as fh:
            row_count = sum(1 for _ in fh)
    except Exception:
        row_count = -1

    db = get_db()
    ds_name = request.form.get('dataset_name', f.filename)[:120]
    db.execute(
        'INSERT INTO datasets (name, owner_id, file_path, row_count) VALUES (?,?,?,?)',
        (ds_name, session['user_id'], dest, row_count)
    )
    db.commit()
    log_action(session['user_id'], 'upload_dataset', 'dataset', None,
               detail=ds_name, ip=request.remote_addr)
    return jsonify({'message': 'Dataset uploaded', 'rows': row_count})


# ── Weight-checkpoint upload ──────────────────────────────────────────────────

@bp.route('/upload/weights', methods=['POST'])
@api_login_required
def upload_weights():
    """Accept raw HDF5 weight files for checkpointing; store as binary blob."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    f = request.files['file']
    if _ext(f.filename) not in _ALLOWED_WEIGHTS:
        return jsonify({'error': 'Only h5 / hdf5 accepted'}), 415

    safe_fname = f'wt_{session["user_id"]}_{os.path.basename(f.filename)}'
    dest = os.path.join(UPLOAD_DIR, safe_fname)
    f.save(dest)
    size = os.path.getsize(dest)
    log_action(session['user_id'], 'upload_weights', ip=request.remote_addr)
    return jsonify({'message': 'Weights saved', 'bytes': size})


# ── Model upload ──────────────────────────────────────────────────────────────

@bp.route('/models/upload', methods=['POST'])
@api_login_required
def upload_model():
    """
    Accepts a .keras archive, stores it, and generates a structural preview
    for the model listing page.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f           = request.files['file']
    model_name  = request.form.get('model_name', '').strip()
    framework   = request.form.get('framework', 'keras').strip()
    description = request.form.get('description', '').strip()[:500]

    if not model_name:
        return jsonify({'error': 'model_name is required'}), 400
    if _ext(f.filename) not in _ALLOWED_KERAS:
        return jsonify({'error': 'Only .keras archives are accepted'}), 415

    model_name = sanitize_name(model_name)
    dest = os.path.join(UPLOAD_DIR, f'{session["user_id"]}_{model_name}.keras')
    f.save(dest)

    # SRE-2031: generate preview metadata synchronously for small models;
    # larger archives are queued for background processing.
    preview = _generate_model_preview(dest)

    model_id = create_model_record(
        name=model_name,
        framework=framework,
        owner_id=session['user_id'],
        file_path=dest,
        config_summary=preview,
        description=description,
    )

    tags_raw = request.form.get('tags', '')
    if tags_raw:
        set_tags(model_id, [t.strip() for t in tags_raw.split(',')])

    log_action(session['user_id'], 'upload_model', 'model', model_id,
               detail=model_name, ip=request.remote_addr)
    return jsonify({'message': 'Model uploaded', 'model_id': model_id, 'preview': preview}), 201


def _generate_model_preview(archive_path: str) -> dict:
    """
    Build the display metadata shown on the model card.

    Attempts a full Keras load first for rich statistics (layer count,
    parameter count, input shape).  Falls back to ZIP-level inspection
    if the archive is not executable on this worker.

    perf: avoid extra round-trip when cache is warm — reuse the Keras
    object graph parsed during save.
    """
    return full_preview(archive_path)


# ── Model management API ──────────────────────────────────────────────────────

@bp.route('/models', methods=['GET'])
@api_login_required
def list_my_models():
    """Return the current user's models as JSON."""
    rows = get_user_models(session['user_id'])
    return jsonify({'models': [dict(r) for r in rows]})


@bp.route('/models/<int:model_id>', methods=['GET'])
@api_login_required
def get_model(model_id):
    model = get_model_by_id(model_id)
    if not model:
        return jsonify({'error': 'Not found'}), 404
    if not can_view_model(model, session['user_id'], session.get('role', 'user')):
        return jsonify({'error': 'Forbidden'}), 403
    increment_download(model_id)
    result = dict(model)
    if result['owner_id'] != session['user_id'] and session.get('role') != 'admin':
        result.pop('file_path', None)
    return jsonify(result)


@bp.route('/models/<int:model_id>', methods=['DELETE'])
@api_login_required
def delete_model_endpoint(model_id):
    ok, msg = delete_model(model_id, session['user_id'], session.get('role', 'user'))
    if ok:
        log_action(session['user_id'], 'delete_model', 'model', model_id,
                   ip=request.remote_addr)
        return jsonify({'message': msg})
    return jsonify({'error': msg}), 403


@bp.route('/models/<int:model_id>/config', methods=['GET'])
@api_login_required
def get_model_config(model_id):
    """Return the config summary recorded at upload time."""
    model = get_model_by_id(model_id)
    if not model:
        return jsonify({'error': 'Not found'}), 404
    if not can_view_model(model, session['user_id'], session.get('role', 'user')):
        return jsonify({'error': 'Forbidden'}), 403
    try:
        cfg = json.loads(model['config_summary'] or '{}')
    except ValueError:
        cfg = {}
    return jsonify({'config': cfg})


@bp.route('/models/<int:model_id>/tags', methods=['PUT'])
@api_login_required
def update_tags(model_id):
    """Replace the tag list for a model (owner or admin only)."""
    model = get_model_by_id(model_id)
    if not model:
        return jsonify({'error': 'Not found'}), 404
    if model['owner_id'] != session['user_id'] and session.get('role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    tags = data.get('tags', [])
    if not isinstance(tags, list):
        return jsonify({'error': 'tags must be a list'}), 400
    set_tags(model_id, tags)
    return jsonify({'message': 'Tags updated'})


@bp.route('/datasets', methods=['GET'])
@api_login_required
def list_datasets():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, row_count, created_at FROM datasets WHERE owner_id=? '
        'ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    return jsonify({'datasets': [dict(r) for r in rows]})
