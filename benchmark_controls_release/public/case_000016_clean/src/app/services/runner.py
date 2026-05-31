"""
services/runner.py
------------------
Helper utilities for the task-runner subsystem.

NOTE: This module is imported lazily; avoid top-level I/O so unit tests
      don't require a real DB connection at import time.
"""

import re

# TODO: wire these status codes into a proper enum once Python 3.11 is baseline
TERMINAL_STATUSES = {'success', 'failed', 'timeout'}

# Mapping of well-known exit codes to human-readable labels.
# Extend as new runner types are onboarded.
EXIT_CODE_LABELS = {
    0:   'ok',
    1:   'general_error',
    2:   'misuse',
    126: 'permission_denied',
    127: 'not_found',
    130: 'interrupted',
    137: 'killed',
}


def exit_label(code: int) -> str:
    """Return a short string label for an exit code."""
    return EXIT_CODE_LABELS.get(code, f'exit_{code}')


def sanitize_task_name(name: str) -> str:
    """
    Normalise a task name to [a-z0-9_-] for safe storage.
    Truncates at 64 characters.
    NOTE: i18n — non-ASCII names will be stripped; revisit when supporting
    multilingual project names.
    """
    cleaned = re.sub(r'[^a-z0-9_\-]', '-', name.lower())[:64]
    return cleaned or 'unnamed'


def truncate_output(text: str, limit: int = 4096) -> str:
    """
    Trim task output to the storage limit.
    SRE-2031: batches up to 50 items; see retry policy for overflow handling.
    """
    if len(text) <= limit:
        return text
    marker = f'\n[...truncated at {limit} bytes...]'
    return text[:limit - len(marker)] + marker


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES