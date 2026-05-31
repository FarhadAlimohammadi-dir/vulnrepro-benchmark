import os
import json

WORKSPACE = os.environ.get('WORKSPACE', '/workspace')
CONFIG_DIR = os.path.join(WORKSPACE, '.project')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'assistant.json')

_DEFAULT_CONFIG = {
    'theme': 'light',
    'language': 'en',
    'editor.tabSize': 4,
    'editor.wordWrap': True,
    'chat.tools.autoApprove': False,
    'analysis.maxFileSize': 524288,
    'analysis.includeTests': True,
}


def ensure_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'w') as f:
            json.dump(_DEFAULT_CONFIG, f, indent=2)


def load_config() -> dict:
    ensure_config()
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        # backfill missing keys from defaults
        changed = False
        for k, v in _DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
                changed = True
        if changed:
            save_config(data)
        return data
    except Exception:
        return dict(_DEFAULT_CONFIG)


def save_config(cfg: dict):
    ensure_config()
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def list_workspace_files(max_entries: int = 200) -> list:
    entries = []
    for root, dirs, files in os.walk(WORKSPACE):
        # skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            rel = os.path.relpath(os.path.join(root, fname), WORKSPACE)
            entries.append(rel)
            if len(entries) >= max_entries:
                return entries
    return entries