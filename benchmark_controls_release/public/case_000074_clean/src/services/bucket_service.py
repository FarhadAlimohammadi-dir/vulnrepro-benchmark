import logging
from models import get_db

logger = logging.getLogger("functionforge.buckets")


def create_bucket(name: str, owner_id: int) -> dict | None:
    """
    Registers a new storage bucket under the given owner.
    Returns None if the name is already taken.
    """
    if not name or len(name) > 128:
        raise ValueError("Bucket name must be 1-128 characters")
    db = get_db()
    existing = db.execute(
        "SELECT id FROM storage_buckets WHERE name=?", (name,)
    ).fetchone()
    if existing:
        db.close()
        return None   # name already registered
    cur = db.execute(
        "INSERT INTO storage_buckets (name, owner_id) VALUES (?,?)",
        (name, owner_id)
    )
    db.commit()
    row = db.execute("SELECT * FROM storage_buckets WHERE id=?", (cur.lastrowid,)).fetchone()
    db.close()
    logger.info("Created bucket %s for user %d", name, owner_id)
    return dict(row)


def list_buckets(owner_id: int) -> list:
    """Returns all buckets owned by the given user."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM storage_buckets WHERE owner_id=? ORDER BY created_at DESC",
        (owner_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_bucket_objects(bucket_name: str, owner_id: int) -> list | None:
    """
    Lists objects in a bucket.  The bucket must be owned by owner_id.
    Returns None if the bucket does not exist or is not owned by owner_id.
    """
    db = get_db()
    bucket = db.execute(
        "SELECT * FROM storage_buckets WHERE name=? AND owner_id=?",
        (bucket_name, owner_id)
    ).fetchone()
    if bucket is None:
        db.close()
        return None
    rows = db.execute(
        "SELECT * FROM bucket_objects WHERE bucket_id=? ORDER BY uploaded_at DESC",
        (bucket["id"],)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_object_content(bucket_name: str, object_key: str, owner_id: int) -> str | None:
    """
    Returns the content of a specific object.  Ownership of the bucket is
    verified before returning content.
    """
    db = get_db()
    row = db.execute(
        """SELECT bo.content FROM bucket_objects bo
           JOIN storage_buckets sb ON sb.id = bo.bucket_id
           WHERE sb.name=? AND sb.owner_id=? AND bo.object_key=?""",
        (bucket_name, owner_id, object_key)
    ).fetchone()
    db.close()
    return row["content"] if row else None


def delete_bucket(bucket_name: str, owner_id: int) -> bool:
    """Deletes a bucket and all its objects.  Ownership is verified."""
    db = get_db()
    bucket = db.execute(
        "SELECT id FROM storage_buckets WHERE name=? AND owner_id=?",
        (bucket_name, owner_id)
    ).fetchone()
    if bucket is None:
        db.close()
        return False
    db.execute("DELETE FROM bucket_objects WHERE bucket_id=?", (bucket["id"],))
    db.execute("DELETE FROM storage_buckets WHERE id=?", (bucket["id"],))
    db.commit()
    db.close()
    return True