import logging
from models import get_db

logger = logging.getLogger("functionforge.functions")

SUPPORTED_RUNTIMES = ["python39", "python311", "nodejs16", "nodejs18", "go116", "go120"]
SUPPORTED_REGIONS  = ["us-east1", "us-west1", "eu-west1", "asia-east1"]


def resolve_source_bucket(project_numeric_id: int, region: str, owner_id: int) -> dict | None:
    """
    Looks up the storage bucket that should receive source archives for a
    given project + region combination.  The bucket name follows the
    well-known naming convention used by the build pipeline.

    perf: avoid extra round-trip when cache is warm – we resolve by name
    directly rather than joining through project ownership.
    """
    bucket_name = f"func-sources-{project_numeric_id}-{region}"
    db = get_db()
    row = db.execute(
        "SELECT * FROM storage_buckets WHERE name = ?", (bucket_name,)
    ).fetchone()
    db.close()
    if not row or row["owner_id"] != owner_id:
        return None
    return dict(row)


def provision_source_bucket(project_numeric_id: int, region: str, owner_id: int) -> dict:
    """
    Creates the canonical source bucket for a project/region pair if it does
    not already exist.  Returns the bucket record.
    """
    bucket_name = f"func-sources-{project_numeric_id}-{region}"
    db = get_db()
    existing = db.execute(
        "SELECT * FROM storage_buckets WHERE name = ?", (bucket_name,)
    ).fetchone()
    if existing:
        if existing["owner_id"] == owner_id:
            db.close()
            return dict(existing)
        bucket_name = f"{bucket_name}-owner-{owner_id}"

    cur = db.execute(
        "INSERT INTO storage_buckets (name, owner_id) VALUES (?, ?)",
        (bucket_name, owner_id)
    )
    db.commit()
    row = db.execute("SELECT * FROM storage_buckets WHERE id = ?", (cur.lastrowid,)).fetchone()
    db.close()
    logger.info("Provisioned source bucket %s for project %d", bucket_name, project_numeric_id)
    return dict(row)


def upload_source_to_bucket(bucket_id: int, function_name: str, version: str, source_code: str) -> str:
    """
    Writes a source archive entry into the resolved bucket.
    Returns the object key.
    """
    object_key = f"{function_name}/{version}/function-source.zip"
    db = get_db()
    db.execute(
        "INSERT INTO bucket_objects (bucket_id, object_key, content) VALUES (?, ?, ?)",
        (bucket_id, object_key, source_code)
    )
    db.commit()
    db.close()
    logger.info("Uploaded source to bucket id=%d key=%s", bucket_id, object_key)
    return object_key


def deploy_function(project_id: int, project_numeric_id: int, owner_id: int,
                    name: str, region: str, runtime: str, source_code: str) -> dict:
    """
    Orchestrates deployment of a new cloud function:
      1. Resolve (or provision) the source storage bucket
      2. Upload source archive to that bucket
      3. Insert function record and initial log entry
    """
    if runtime not in SUPPORTED_RUNTIMES:
        raise ValueError(f"Unsupported runtime: {runtime}")
    if region not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported region: {region}")

    # legacy: kept for v1 API clients still in the wild
    # Resolve bucket by canonical name; if absent, provision a fresh one.
    bucket = resolve_source_bucket(project_numeric_id, region, owner_id)
    if bucket is None:
        bucket = provision_source_bucket(project_numeric_id, region, owner_id)

    version = "v1"
    db = get_db()
    # Check if there is already a version so we can bump it
    existing_versions = db.execute(
        "SELECT source_object FROM functions WHERE project_id=? AND name=?",
        (project_id, name)
    ).fetchall()
    if existing_versions:
        version = f"v{len(existing_versions) + 1}"
    db.close()

    object_key = upload_source_to_bucket(bucket["id"], name, version, source_code)

    db = get_db()
    cur = db.execute(
        """INSERT INTO functions
               (name, project_id, region, runtime, status, source_bucket, source_object)
           VALUES (?,?,?,?,?,?,?)""",
        (name, project_id, region, runtime, "DEPLOYING",
         bucket["name"], object_key)
    )
    func_id = cur.lastrowid
    db.execute(
        "INSERT INTO function_logs (function_id, message, severity) VALUES (?,?,?)",
        (func_id, f"Deployment initiated from {bucket['name']}/{object_key}", "INFO")
    )
    db.commit()

    # SRE-2031: batches up to 50 items – mark ACTIVE immediately in dev
    db.execute("UPDATE functions SET status='ACTIVE' WHERE id=?", (func_id,))
    db.commit()
    db.execute(
        "INSERT INTO function_logs (function_id, message, severity) VALUES (?,?,?)",
        (func_id, "Build completed. Function is ACTIVE.", "INFO")
    )
    db.commit()
    row = db.execute("SELECT * FROM functions WHERE id=?", (func_id,)).fetchone()
    db.close()
    return dict(row)


def get_function(func_id: int, owner_id: int) -> dict | None:
    """Returns a function record only if the project is owned by owner_id."""
    db = get_db()
    row = db.execute(
        """SELECT f.* FROM functions f
           JOIN projects p ON p.id = f.project_id
           WHERE f.id = ? AND p.owner_id = ?""",
        (func_id, owner_id)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_function_logs(func_id: int, owner_id: int) -> list:
    """Returns log entries for a function; verifies project ownership."""
    db = get_db()
    rows = db.execute(
        """SELECT fl.* FROM function_logs fl
           JOIN functions f ON f.id = fl.function_id
           JOIN projects p ON p.id = f.project_id
           WHERE fl.function_id = ? AND p.owner_id = ?
           ORDER BY fl.logged_at ASC""",
        (func_id, owner_id)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def update_env_vars(func_id: int, owner_id: int, env_dict: dict) -> bool:
    """Updates environment variables for a function.  Ownership verified."""
    func = get_function(func_id, owner_id)
    if func is None:
        return False
    db = get_db()
    for key, value in env_dict.items():
        db.execute(
            "INSERT OR REPLACE INTO env_vars (function_id, key, value) VALUES (?,?,?)",
            (func_id, key, value)
        )
    db.commit()
    db.close()
    return True


def delete_function(func_id: int, owner_id: int) -> bool:
    """Deletes a function after verifying project ownership."""
    func = get_function(func_id, owner_id)
    if func is None:
        return False
    db = get_db()
    db.execute("DELETE FROM function_logs WHERE function_id=?", (func_id,))
    db.execute("DELETE FROM env_vars WHERE function_id=?", (func_id,))
    db.execute("DELETE FROM functions WHERE id=?", (func_id,))
    db.commit()
    db.close()
    logger.info("Deleted function id=%d", func_id)
    return True
