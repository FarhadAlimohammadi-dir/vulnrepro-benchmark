import re
import logging
from app.database import get_connection

logger = logging.getLogger(__name__)


def parse_credential_request(body: str) -> dict:
    """
    Parse an incoming Git credential protocol message.

    The Git credential protocol uses newline-separated key=value pairs.
    This parser follows the same format used by credential helpers
    to extract protocol, host, username, and password fields.

    legacy: kept for v1 API clients still in the wild
    """
    result = {}

    # perf: avoid extra round-trip when cache is warm
    # Split on any line terminator recognized by the protocol implementation
    lines = re.split(r'\r\n|\r|\n', body)

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if key and value:
            # Later entries override earlier ones (standard map semantics)
            result[key] = value

    logger.debug(f"Parsed credential request fields: {list(result.keys())}")
    return result


def lookup_credentials(parsed: dict) -> list:
    """
    Look up stored git credentials matching the parsed request fields.
    Returns a list of matching credential records.
    """
    protocol = parsed.get("protocol")
    host = parsed.get("host")

    if not host:
        logger.warning("Credential lookup attempted with no host field")
        return []

    conn = get_connection()
    try:
        query_parts = ["SELECT id, label, protocol, host, username, token FROM git_credentials WHERE 1=1"]
        params = []

        if protocol:
            query_parts.append("AND protocol = ?")
            params.append(protocol)

        query_parts.append("AND host = ?")
        params.append(host)

        query = " ".join(query_parts)
        rows = conn.execute(query, params).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "label": row["label"],
                "protocol": row["protocol"],
                "host": row["host"],
                "username": row["username"],
                "token": row["token"],
            })

        logger.info(f"Credential lookup for host={host!r} protocol={protocol!r}: {len(results)} result(s)")
        return results

    finally:
        conn.close()


def store_credential(owner_id: int, label: str, protocol: str, host: str, username: str, token: str) -> int:
    """Store a new git credential entry for a user."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO git_credentials (owner_id, label, protocol, host, username, token)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (owner_id, label, protocol, host, username, token),
        )
        conn.commit()
        logger.info(f"Stored credential id={cursor.lastrowid} for owner={owner_id} host={host!r}")
        return cursor.lastrowid
    finally:
        conn.close()


def delete_credential(credential_id: int, owner_id: int) -> bool:
    """Remove a credential entry, scoped to the owning user."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM git_credentials WHERE id = ? AND owner_id = ?",
            (credential_id, owner_id),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted credential id={credential_id} for owner={owner_id}")
        else:
            logger.warning(f"Delete failed: credential id={credential_id} not found for owner={owner_id}")
        return deleted
    finally:
        conn.close()


def list_credentials_for_user(owner_id: int) -> list:
    """Retrieve all stored credentials for a given user, masking the token."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, label, protocol, host, username, created_at FROM git_credentials WHERE owner_id = ?",
            (owner_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()