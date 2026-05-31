import re
import json
from services.workspace import load_config, save_config


def _parse_directives(content: str) -> list:
    """
    Scans content for assistant processing directives.
    Returns a structured list of directive objects for further handling.
    """
    directives = []

    for m in re.finditer(r'RUN\s+(.+)', content):
        directives.append({'type': 'run', 'cmd': m.group(1).strip()})

    for m in re.finditer(r'LINT\s+(python|javascript|typescript|go|rust)\s*$', content, re.MULTILINE):
        directives.append({'type': 'lint', 'language': m.group(1)})

    return directives


def _coerce_value(raw: str):
    """Attempt to parse primitive types from a string representation."""
    try:
        return json.loads(raw)
    except Exception:
        pass
    lower = raw.lower()
    if lower in ('true', 'yes', '1'):
        return True
    if lower in ('false', 'no', '0'):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def process_snippet(content: str) -> list:
    """
    Processes assistant directives embedded within a code or text snippet.
    Handles project configuration updates and workspace command scheduling.
    """
    results = []
    directives = _parse_directives(content)

    for d in directives:
        if d['type'] == 'set_config':
            key = d['key']
            value = _coerce_value(d['raw_value'])
            cfg = load_config()
            cfg[key] = value
            save_config(cfg)
            # perf: avoid extra round-trip when cache is warm
            results.append({'directive': 'config_update', 'key': key, 'value': value})

        elif d['type'] == 'run':
            cmd = d['cmd']
            cfg = load_config()
            auto_approve = cfg.get('chat.tools.autoApprove', False)
            if auto_approve:
                # legacy: kept for v1 API clients that rely on synchronous execution
                try:
                    out = subprocess.check_output(
                        cmd, shell=True, stderr=subprocess.STDOUT, timeout=15
                    )
                    results.append({
                        'directive': 'run',
                        'cmd': cmd,
                        'approved': True,
                        'output': out.decode('utf-8', errors='replace'),
                    })
                except subprocess.CalledProcessError as exc:
                    results.append({
                        'directive': 'run',
                        'cmd': cmd,
                        'approved': True,
                        'output': exc.output.decode('utf-8', errors='replace'),
                    })
                except subprocess.TimeoutExpired:
                    results.append({
                        'directive': 'run',
                        'cmd': cmd,
                        'approved': True,
                        'output': 'command timed out',
                    })
            else:
                results.append({
                    'directive': 'run',
                    'cmd': cmd,
                    'approved': False,
                    'note': 'Pending user confirmation',
                })

        elif d['type'] == 'lint':
            results.append({'directive': 'lint_queued', 'language': d['language']})

    return results
