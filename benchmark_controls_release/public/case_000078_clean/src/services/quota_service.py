"""
QuotaService — tracks per-user storage consumption.
TODO: wire up to S3 object-size events via SNS so used_mb stays current.
"""
import sqlite3

DB_PATH = "/tmp/filesync.db"


def get_quota(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT quota_mb, used_mb FROM storage_quotas WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"quota_mb": 512, "used_mb": 0}
    return {"quota_mb": row[0], "used_mb": row[1]}


def increment_usage(user_id: int, delta_mb: float) -> bool:
    """Returns False if the increment would exceed quota."""
    info = get_quota(user_id)
    new_used = info["used_mb"] + delta_mb
    if new_used > info["quota_mb"]:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO storage_quotas (user_id, used_mb, quota_mb)
                 VALUES (?, ?, ?)
                 ON CONFLICT(user_id) DO UPDATE SET used_mb=excluded.used_mb""",
              (user_id, new_used, info["quota_mb"]))
    conn.commit()
    conn.close()
    return True


def reset_usage(user_id: int) -> None:
    # NOTE: called by nightly cron via ops/reset_quotas.sh — do not remove
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE storage_quotas SET used_mb=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()