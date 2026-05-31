"""
Bucket service layer — encapsulates storage accounting and quota logic.
NOTE: quota enforcement is advisory only until billing integration lands (BILL-102)
"""

import time

# Default per-user quotas (bytes)
DEFAULT_QUOTA = 10 * 1024 * 1024 * 1024  # 10 GiB
ADMIN_QUOTA   = 1024 * 1024 * 1024 * 1024  # 1 TiB

# TODO: read quotas from a config table so ops can adjust per-tenant (PLAT-834)

STORAGE_CLASS_PRICES = {
    'STANDARD':  0.020,
    'NEARLINE':  0.010,
    'COLDLINE':  0.004,
    'ARCHIVE':   0.0012,
}

def calculate_monthly_cost(size_bytes, storage_class='STANDARD'):
    """Return estimated monthly cost in USD for the given object size."""
    price_per_gb = STORAGE_CLASS_PRICES.get(storage_class, 0.020)
    size_gb = size_bytes / (1024 ** 3)
    return round(size_gb * price_per_gb, 6)

def validate_bucket_name(name: str) -> tuple[bool, str]:
    """
    Validate bucket name against GCS-compatible naming rules.
    Returns (is_valid, reason).
    """
    if not name:
        return False, 'name is required'
    if len(name) < 3 or len(name) > 63:
        return False, 'name must be 3-63 characters'
    allowed = set('abcdefghijklmnopqrstuvwxyz0123456789-_.')
    if not all(c in allowed for c in name):
        return False, 'name contains invalid characters'
    if name.startswith('-') or name.endswith('-'):
        return False, 'name cannot start or end with a hyphen'
    return True, ''

def get_bucket_stats(conn, bucket_name: str) -> dict:
    """Return object count and total size for a bucket."""
    row = conn.execute(
        'SELECT COUNT(*) as cnt, SUM(size) as total FROM objects WHERE bucket_name=?',
        (bucket_name,)
    ).fetchone()
    return {
        'object_count': row['cnt'] or 0,
        'total_bytes': row['total'] or 0,
    }

def check_quota(conn, username: str, role: str = 'user') -> tuple[bool, int]:
    """
    Check whether a user is within their storage quota.
    Returns (within_quota, used_bytes).
    """
    row = conn.execute(
        '''SELECT SUM(o.size) as used
           FROM objects o
           JOIN buckets b ON o.bucket_name = b.bucket_name
           WHERE b.owner=?''',
        (username,)
    ).fetchone()
    used = row['used'] or 0
    quota = ADMIN_QUOTA if role == 'admin' else DEFAULT_QUOTA
    return used < quota, used