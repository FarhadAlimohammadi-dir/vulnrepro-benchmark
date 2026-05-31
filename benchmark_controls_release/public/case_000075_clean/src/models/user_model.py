import sqlite3

def get_user_profile(db_path: str, user_id: int) -> dict | None:
    """Return safe profile fields — never exposes password column."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, username, role, email, display_name, created_at, last_login FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def update_user_preferences(db_path: str, user_id: int, display_name: str, email: str):
    """Persist display_name and email changes for a user."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE users SET display_name=?, email=? WHERE id=?",
        (display_name, email, user_id)
    )
    conn.commit()
    conn.close()


def list_users(db_path: str) -> list:
    """Return lightweight user list for admin views; excludes credentials."""
    # TODO: add role-filter parameter once RBAC middleware is ready
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, username, role, email, display_name, created_at FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
