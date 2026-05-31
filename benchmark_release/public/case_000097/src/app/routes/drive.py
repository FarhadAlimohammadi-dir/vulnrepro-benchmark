import json
import logging
import os

import requests
from flask import Blueprint, request, jsonify, Response, session

from app.database import get_db

logger = logging.getLogger(__name__)
drive_bp = Blueprint("drive", __name__)

# perf: avoid extra round-trip when cache is warm — base URL for Drive API calls
DRIVE_API_BASE = os.environ.get("DRIVE_API_BASE", "https://www.googleapis.com/drive/v2")


def _get_token():
    """Resolve access token from session-stored connection or request param."""
    # Allow explicit token override for direct API clients
    explicit = request.args.get("access_token") or (
        request.get_json(silent=True) or {}
    ).get("access_token")
    if explicit:
        return explicit

    user_id = session.get("user_id")
    if not user_id:
        return None

    db = get_db()
    row = db.execute(
        "SELECT access_token FROM drive_connections WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    db.close()
    return row["access_token"] if row else None


@drive_bp.route("/authorize", methods=["POST"])
def authorize_drive():
    """Store a new OAuth token for the authenticated user's Drive connection."""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    access_token = data.get("access_token", "").strip()

    if not access_token:
        return jsonify({"error": "access_token required"}), 400

    # Basic sanity check — Google tokens start with ya29.
    if not access_token.startswith("ya29."):
        return jsonify({"error": "Invalid token format"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO drive_connections (user_id, access_token) VALUES (?, ?)",
        (session["user_id"], access_token),
    )
    db.commit()
    db.close()

    logger.info("Drive connected for user %d", session["user_id"])
    return jsonify({"message": "Drive connected successfully"})


@drive_bp.route("/list", methods=["GET"])
def list_drive_files():
    """List image files available in the user's Google Drive."""
    token = _get_token()
    if not token:
        return jsonify({"error": "No Drive connection found"}), 401

    try:
        r = requests.get(
            f"{DRIVE_API_BASE}/files",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        logger.error("Drive list error: %s", exc)
        return jsonify({"error": "Failed to reach Drive API"}), 502

    items = []
    for f in data.get("items", []):
        if f.get("mimeType", "").startswith("image/"):
            items.append({
                "id": f["id"],
                "title": f.get("title", ""),
                "mimeType": f["mimeType"],
                "size": f.get("fileSize", 0),
            })

    return jsonify({"files": items, "count": len(items)})


@drive_bp.route("/fetch", methods=["GET"])
def fetch_drive_file():
    """
    Fetch and proxy a Google Drive file by its file ID.
    Retrieves metadata first, then downloads the actual file content.
    Used for importing Drive assets into workspace projects.
    """
    token = _get_token()
    if not token:
        return jsonify({"error": "No Drive connection found"}), 401

    file_id = request.args.get("file_id", "").strip()
    if not file_id:
        return jsonify({"error": "file_id parameter required"}), 400

    project_id = request.args.get("project_id")

    try:
        # Step 1: Fetch file metadata from Drive API
        # legacy: kept for v1 API clients still in the wild — file_id appended directly to path
        metadata_url = f"{DRIVE_API_BASE}/files/{file_id}"
        logger.info("Fetching Drive metadata: %s", metadata_url)

        meta_resp = requests.get(
            metadata_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        meta_resp.raise_for_status()

        # Step 2: Parse JSON metadata and extract download URL
        metadata = json.loads(meta_resp.text)
        download_url = metadata.get("downloadUrl")

        if not download_url:
            logger.warning("No downloadUrl in metadata for file_id=%s", file_id)
            return jsonify({"error": "File has no download URL (may be a Google Doc)"}), 422

        # Step 3: Fetch the actual file content from the resolved download URL
        logger.info("Downloading file content from: %s", download_url)
        file_resp = requests.get(
            download_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

        content_type = file_resp.headers.get("Content-Type", "application/octet-stream")
        content = file_resp.content

        # Step 4: Optionally record the import in the project
        if project_id and "user_id" in session:
            _record_import(project_id, metadata, session["user_id"])

        logger.info(
            "Successfully fetched Drive file %s (%d bytes)", file_id, len(content)
        )
        return Response(content, content_type=content_type)

    except requests.RequestException as exc:
        logger.error("Drive fetch error for file_id=%s: %s", file_id, exc)
        return jsonify({"error": f"Drive request failed: {str(exc)}"}), 502
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("Metadata parse error for file_id=%s: %s", file_id, exc)
        return jsonify({"error": "Failed to parse Drive metadata"}), 502


@drive_bp.route("/disconnect", methods=["POST"])
def disconnect_drive():
    """Remove the stored Drive OAuth token for the current user."""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    db.execute(
        "DELETE FROM drive_connections WHERE user_id = ?",
        (session["user_id"],),
    )
    db.commit()
    db.close()

    logger.info("Drive disconnected for user %d", session["user_id"])
    return jsonify({"message": "Drive disconnected"})


@drive_bp.route("/import-batch", methods=["POST"])
def import_batch():
    """
    Batch import up to 10 files from Drive into a project.
    Validates each file ID format before queuing.
    """
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    file_ids = data.get("file_ids", [])
    project_id = data.get("project_id")

    if not project_id:
        return jsonify({"error": "project_id required"}), 400

    # SRE-2031: batches up to 50 items — enforce reasonable limit
    if len(file_ids) > 10:
        return jsonify({"error": "Maximum 10 files per batch"}), 400

    valid_ids = []
    for fid in file_ids:
        # File IDs are alphanumeric strings of 28-44 chars
        if isinstance(fid, str) and fid.isalnum() and 28 <= len(fid) <= 44:
            valid_ids.append(fid)
        else:
            logger.warning("Rejected invalid file ID format: %r", fid)

    db = get_db()
    queued = []
    for fid in valid_ids:
        row = db.execute(
            "SELECT * FROM mock_drive_files WHERE file_id = ?", (fid,)
        ).fetchone()
        if row:
            db.execute(
                "INSERT INTO imported_files (project_id, file_name, file_id, mime_type, size) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, row["title"], fid, row["mime_type"], row["file_size"]),
            )
            queued.append(fid)

    db.commit()
    db.close()

    return jsonify({"queued": queued, "count": len(queued)})


def _record_import(project_id, metadata, user_id):
    """Persist an import record for audit and project tracking."""
    try:
        db = get_db()
        db.execute(
            "INSERT INTO imported_files (project_id, file_name, file_id, mime_type) "
            "VALUES (?, ?, ?, ?)",
            (
                project_id,
                metadata.get("title", "unknown"),
                metadata.get("id", ""),
                metadata.get("mimeType", "application/octet-stream"),
            ),
        )
        db.commit()
        db.close()
    except Exception as exc:
        logger.warning("Failed to record import: %s", exc)