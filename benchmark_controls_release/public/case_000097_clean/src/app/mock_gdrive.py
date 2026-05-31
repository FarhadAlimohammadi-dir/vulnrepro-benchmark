"""
Mock Google Drive API v2 — simulates drive.googleapis.com for local dev/testing.
Supports file metadata lookup and raw media download (alt=media).
"""

import json
import logging
import os
import sqlite3
from flask import Blueprint, request, jsonify, Response

from app.database import get_db

logger = logging.getLogger(__name__)

mock_gdrive_bp = Blueprint("mock_gdrive", __name__)


def _get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.args.get("access_token", "")


@mock_gdrive_bp.route("/files/", methods=["GET"])
@mock_gdrive_bp.route("/files", methods=["GET"])
def list_files():
    """List Drive files owned by the authenticated user."""
    token = _get_bearer_token()
    if not token:
        return jsonify({"error": {"code": 401, "message": "Unauthorized"}}), 401

    db = get_db()
    rows = db.execute(
        "SELECT * FROM mock_drive_files WHERE owner_token = ?", (token,)
    ).fetchall()
    db.close()

    items = []
    for row in rows:
        items.append({
            "id": row["file_id"],
            "title": row["title"],
            "mimeType": row["mime_type"],
            "fileSize": str(row["file_size"]),
            "downloadUrl": row["download_url"],
        })

    return jsonify({"kind": "drive#fileList", "items": items})


@mock_gdrive_bp.route("/files/create", methods=["POST"])
def create_test_file():
    """
    Test fixture endpoint — insert a mock Drive file record for integration testing.
    Used by the test suite to seed specific file payloads.
    """
    fixture_token = os.environ.get("MOCK_GDRIVE_FIXTURE_TOKEN")
    supplied = request.headers.get("X-Fixture-Token", "")
    if not fixture_token or supplied != fixture_token:
        return jsonify({"error": {"code": 404, "message": "Not found"}}), 404

    data = request.get_json(silent=True) or {}

    required = ["file_id", "owner_token", "title", "mime_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    db = get_db()
    try:
        db.execute(
            """INSERT INTO mock_drive_files
               (file_id, owner_token, title, mime_type, file_size, download_url, body_content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["file_id"],
                data["owner_token"],
                data["title"],
                data["mime_type"],
                data.get("file_size", 0),
                data.get("download_url"),
                data.get("body_content"),
            ),
        )
        db.commit()
        db.close()
        return jsonify({"message": "File created", "file_id": data["file_id"]}), 201
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"message": "File already exists", "file_id": data["file_id"]}), 409


@mock_gdrive_bp.route("/files/<path:file_id>", methods=["GET"])
def get_file_metadata(file_id):
    """
    Return file metadata JSON, or raw file body when alt=media is requested.
    Mirrors the real Drive API behaviour for v2/files/{fileId}?alt=media.
    """
    token = _get_bearer_token()
    if not token:
        return jsonify({"error": {"code": 401, "message": "Unauthorized"}}), 401

    alt = request.args.get("alt", "")

    # Strip any extra query string that came in via path (already parsed by Flask)
    clean_file_id = file_id.split("?")[0]

    db = get_db()
    row = db.execute(
        "SELECT * FROM mock_drive_files WHERE file_id = ? AND owner_token = ?",
        (clean_file_id, token),
    ).fetchone()
    db.close()

    if not row:
        logger.warning("Mock Drive: file not found: %s (clean: %s)", file_id, clean_file_id)
        return jsonify({"error": {"code": 404, "message": "File not found"}}), 404

    # When alt=media is specified, return the raw stored body content instead of metadata JSON
    if alt == "media":
        body = row["body_content"]
        if body is None:
            # Default placeholder for files without stored body
            body = json.dumps({
                "kind": "drive#file",
                "id": row["file_id"],
                "title": row["title"],
                "placeholder": True,
            })
        logger.info("Mock Drive: serving raw body for file %s (alt=media)", clean_file_id)
        return Response(body, content_type="application/json")

    # Default: return JSON metadata object
    metadata = {
        "kind": "drive#file",
        "id": row["file_id"],
        "title": row["title"],
        "mimeType": row["mime_type"],
        "fileSize": str(row["file_size"]),
        "downloadUrl": row["download_url"],
        "selfLink": f"https://www.googleapis.com/drive/v2/files/{row['file_id']}",
    }
    return jsonify(metadata)
