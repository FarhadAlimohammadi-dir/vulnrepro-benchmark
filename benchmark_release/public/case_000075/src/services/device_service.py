import sqlite3
import time

# TODO: cache device list in Redis — currently hits DB on every request

def get_device_list(db_path: str) -> list:
    """Return summary info for all devices; omits PIN column."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, location, status, firmware_version, last_accessed FROM devices ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_info(db_path: str, device_id: int) -> dict | None:
    """Fetch a single device record; omits PIN column."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name, location, status, firmware_version, last_accessed, owner_id FROM devices WHERE id=?",
        (device_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def mark_device_accessed(db_path: str, device_id: int):
    """Update the last_accessed timestamp for a device."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE devices SET last_accessed=? WHERE id=?",
        (int(time.time()), device_id)
    )
    conn.commit()
    conn.close()


def set_device_status(db_path: str, device_id: int, status: str) -> bool:
    """Set device status to active/inactive/maintenance."""
    allowed = {'active', 'inactive', 'maintenance'}
    if status not in allowed:
        return False
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE devices SET status=? WHERE id=?", (status, device_id))
    conn.commit()
    conn.close()
    return True