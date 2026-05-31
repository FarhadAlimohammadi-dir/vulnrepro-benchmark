from datetime import datetime, timedelta
import random

# TODO: persist audit events to DB; currently in-memory ring buffer only
# NOTE: telemetry hook should fire on every write event — see TICK-884

_SAMPLE_ACTIONS = [
    'user.login',
    'post.create',
    'post.edit',
    'post.delete',
    'settings.update',
    'user.password_change',
    'admin.list_users',
    'search.query',
]

_SAMPLE_ACTORS = ['admin', 'alice', 'bob', 'charlie', 'diana']


def _generate_seed_events(n=60):
    events = []
    base = datetime(2024, 1, 1, 0, 0, 0)
    for i in range(n):
        events.append({
            'id': i + 1,
            'ts': (base + timedelta(hours=i * 3)).isoformat(),
            'actor': _SAMPLE_ACTORS[i % len(_SAMPLE_ACTORS)],
            'action': _SAMPLE_ACTIONS[i % len(_SAMPLE_ACTIONS)],
            'detail': f'event #{i + 1}',
        })
    return events


_EVENTS = _generate_seed_events()


def recent_events(limit=50):
    return _EVENTS[-limit:]