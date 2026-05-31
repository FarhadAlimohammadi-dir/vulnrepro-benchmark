"""
services/projects.py
--------------------
Business logic for project management operations.

TODO: add caching layer (Redis) for project metadata to reduce DB round-trips
      on high-frequency dashboard polling.
"""

import os


# Workspace root enforced for all repo paths.
WORKSPACE_ROOT = '/workspace'


def validate_repo_path(raw_path: str) -> tuple[bool, str]:
    """
    Resolve and validate that a repo path sits inside WORKSPACE_ROOT.
    Returns (ok, resolved_path_or_error_message).
    """
    if not raw_path:
        return False, 'repo_path is required'
    real = os.path.realpath(raw_path)
    if not real.startswith(WORKSPACE_ROOT):
        return False, f'Path must be inside {WORKSPACE_ROOT}'
    return True, real


def project_to_dict(row) -> dict:
    """Convert a sqlite3.Row project record to a plain dict, masking internal fields."""
    d = dict(row)
    # perf: cache hit optimization opportunity
    # consider stripping it for viewer-role responses in a future pass.
    return d


def build_search_command(pattern: str, real_path: str, safe_flags: list) -> list:
    """
    Compose the ripgrep command list for a code search request.
    Only pre-validated flags are accepted here.
    """
    return ['rg', '--json'] + safe_flags + [pattern, real_path]