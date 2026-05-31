import time
import collections

# NOTE: In production this would ship events to Cloud Logging / BigQuery.
# Local in-memory ring buffer is only for development convenience.

_EVENT_BUFFER = collections.deque(maxlen=500)


def record_event(event_type: str, metadata: dict = None):
    """Append a structured event to the in-memory audit buffer."""
    entry = {
        'eventType': event_type,
        'timestamp': int(time.time()),
        'metadata': metadata or {}
    }
    _EVENT_BUFFER.appendleft(entry)


def log_request_event(action: str, limit: int = 50) -> list:
    """Retrieve recent events from buffer, newest first."""
    # TODO: add filtering by eventType and time range for compliance queries
    events = list(_EVENT_BUFFER)
    return events[:limit]


def seed_sample_events():
    """Populate buffer with representative events for demo purposes."""
    sample = [
        ('api_key_validated', {'project': 'chat-client-prod', 'result': 'ok'}),
        ('discovery_requested', {'host': 'people-pa.googleapis.com', 'result': 'ok'}),
        ('people_list', {'pageSize': 10, 'result': 'ok'}),
        ('people_search', {'query': 'anya', 'hits': 1}),
        ('api_key_validated', {'project': 'contacts-widget', 'result': 'ok'}),
        ('discovery_requested', {'host': 'people-pa.googleapis.com', 'result': 'ok'}),
        ('people_get', {'resourceName': 'people/c1003', 'result': 'ok'}),
        ('people_list', {'pageSize': 25, 'result': 'ok'}),
        ('api_key_missing', {'ip': '10.0.0.55', 'result': 'denied'}),
        ('people_search', {'query': 'marcus', 'hits': 1}),
    ]
    for evt, meta in sample:
        record_event(evt, meta)


seed_sample_events()