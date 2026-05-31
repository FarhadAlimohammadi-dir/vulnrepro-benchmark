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
_TRUSTED_MODULE_PREFIXES = ('keras', 'keras.', 'tensorflow', 'tensorflow.')


def validate_keras_archive(archive_path: str) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            names = set(zf.namelist())
            if 'config.json' not in names or 'metadata.json' not in names:
                return False, 'Archive is missing required model metadata'
            cfg = json.loads(zf.read('config.json'))
    except zipfile.BadZipFile:
        return False, 'Not a valid ZIP/keras archive'
    except Exception:
        return False, 'Unable to inspect archive metadata'

    stack = [cfg]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            module = item.get('module')
            if module and not str(module).startswith(_TRUSTED_MODULE_PREFIXES):
                return False, 'Archive references an unsupported model module'
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return True, ''


def fast_preview(archive_path: str) -> dict:
    """
    Open the ZIP and read config.json / metadata.json without executing
    any model code.  Returns a dict suitable for JSON serialisation.
    """
    result = {}
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            names = zf.namelist()
            result['archive_files'] = names

            if 'metadata.json' in names:
                meta = json.loads(zf.read('metadata.json'))
                result['keras_version'] = meta.get('keras_version', 'unknown')
                result['date_saved'] = meta.get('date_saved', 'unknown')

            if 'config.json' in names:
                cfg = json.loads(zf.read('config.json'))
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
