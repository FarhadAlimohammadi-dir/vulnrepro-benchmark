import sqlite3
import os
from contextlib import contextmanager

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/docuvault.db')

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def query_one(sql, params=()):
    with get_db() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

def query_all(sql, params=()):
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def execute(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid