"""
Archive-inspection helpers for .keras model files.

A .keras file is a ZIP archive containing:
  config.json      — layer graph and hyper-parameters
  metadata.json    — Keras version, save date
  model.weights.h5 — HDF5 weight tensors

This module provides two code paths:
  1. fast_preview()  — pure-ZIP inspection, no execution (used for listings)
  2. full_preview()  — delegates to Keras for rich metadata extraction
"""
import json
import zipfile


# Fields we surface from config.json in the fast path
_SAFE_SCALAR_KEYS = ('class_name', 'name', 'trainable', 'dtype')
_MAX_ZIP_ENTRIES = 32
_MAX_JSON_MEMBER_BYTES = 256 * 1024
_MAX_COMPRESSION_RATIO = 100


def _read_small_json_member(zf: zipfile.ZipFile, name: str):
    info = zf.getinfo(name)
    compressed = max(info.compress_size, 1)
    if info.file_size > _MAX_JSON_MEMBER_BYTES:
        raise ValueError(f'{name} is too large')
    if info.file_size / compressed > _MAX_COMPRESSION_RATIO:
        raise ValueError(f'{name} compression ratio is too high')
    with zf.open(name) as member:
        data = member.read(_MAX_JSON_MEMBER_BYTES + 1)
    if len(data) > _MAX_JSON_MEMBER_BYTES:
        raise ValueError(f'{name} is too large')
    return json.loads(data)


def fast_preview(archive_path: str) -> dict:
    """
    Open the ZIP and read config.json / metadata.json without executing
    any model code.  Returns a dict suitable for JSON serialisation.
    """
    result = {}
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            names = zf.namelist()
            if len(names) > _MAX_ZIP_ENTRIES:
                raise ValueError('Archive contains too many files')
            result['archive_files'] = names

            if 'metadata.json' in names:
                meta = _read_small_json_member(zf, 'metadata.json')
                result['keras_version'] = meta.get('keras_version', 'unknown')
                result['date_saved'] = meta.get('date_saved', 'unknown')

            if 'config.json' in names:
                cfg = _read_small_json_member(zf, 'config.json')
                for k in _SAFE_SCALAR_KEYS:
                    if k in cfg and isinstance(cfg[k], (str, bool, int, float)):
                        result[k] = cfg[k]
    except zipfile.BadZipFile:
        result['error'] = 'Not a valid ZIP/keras archive'
    except Exception as e:
        result['error'] = str(e)[:200]
    return result


def full_preview(archive_path: str) -> dict:
    """
    Load the model via Keras to extract layer counts and parameter totals.
    Falls back to fast_preview() if loading fails.

    perf: avoid extra round-trip when cache is warm — Keras caches the
    deserialized layer graph internally after the first call.
    """
    try:
        import keras
        # legacy: kept for v1 API clients that expect layer/param counts
        model = keras.saving.load_model(archive_path, compile=False)
        return {
            'layers': len(model.layers),
            'params': int(model.count_params()),
            'input_shape': (
                str(model.input_shape) if hasattr(model, 'input_shape') else 'n/a'
            ),
            'class_name': model.__class__.__name__,
        }
    except Exception as e:
        fallback = fast_preview(archive_path)
        fallback['load_error'] = str(e)[:200]
        return fallback
