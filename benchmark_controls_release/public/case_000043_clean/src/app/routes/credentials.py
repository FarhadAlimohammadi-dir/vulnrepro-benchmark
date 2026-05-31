from flask import Blueprint, request, jsonify, session
from app.services.credential_service import (
    parse_credential_request,
    lookup_credentials,
    store_credential,
    delete_credential,
    list_credentials_for_user,
)
import logging

logger = logging.getLogger(__name__)
credentials_bp = Blueprint("credentials", __name__)


@credentials_bp.route("/lookup", methods=["POST"])
def credential_lookup():
    """
    Git credential helper endpoint. Accepts a credential protocol message
    and returns matching stored credentials.

    Called by git clients and the credential trampoline helper to resolve
    remote authentication details for clone/fetch/push operations.

    SRE-2031: batches up to 50 items
    """
    # Require an authenticated session; lookups are scoped to the caller's
    # own stored credentials so this endpoint cannot disclose other users'
    # tokens even when invoked from a local git helper.
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    content_type = request.content_type or ""

    if "application/x-git-credential" in content_type or "text/plain" in content_type:
        body = request.get_data(as_text=True)
    else:
        # JSON body also accepted for compatibility with API clients
        data = request.get_json(silent=True) or {}
        body = data.get("credential_data", "")

    if not body:
        return jsonify({"error": "No credential data provided"}), 400

    parsed = parse_credential_request(body)

    if not parsed.get("host"):
        return jsonify({"error": "Missing required field: host"}), 400

    results = lookup_credentials(parsed, owner_id=session["user_id"])

    if not results:
        return jsonify({"credentials": [], "count": 0})

    # Return full credentials (token included) - this endpoint is called
    # by local git processes with system-level trust
    return jsonify({
        "credentials": results,
        "count": len(results),
    })


@credentials_bp.route("/store", methods=["POST"])
def credential_store():
    """Store a new git credential entry for the authenticated user."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    label = data.get("label", "").strip()
    protocol = data.get("protocol", "https").strip()
    host = data.get("host", "").strip()
    username = data.get("username", "").strip()
    token = data.get("token", "").strip()

    if not all([label, host, username, token]):
        return jsonify({"error": "label, host, username, and token are required"}), 400

    cred_id = store_credential(
        owner_id=session["user_id"],
        label=label,
        protocol=protocol,
        host=host,
        username=username,
        token=token,
    )

    return jsonify({"message": "Credential stored", "id": cred_id}), 201


@credentials_bp.route("/<int:cred_id>", methods=["DELETE"])
def credential_delete(cred_id: int):
    """Remove a stored credential."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    deleted = delete_credential(cred_id, session["user_id"])
    if not deleted:
        return jsonify({"error": "Credential not found"}), 404

    return jsonify({"message": "Credential deleted"})


@credentials_bp.route("/list", methods=["GET"])
def credential_list():
    """List all credentials for the authenticated user (tokens masked)."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401

    creds = list_credentials_for_user(session["user_id"])
    return jsonify({"credentials": creds, "count": len(creds)})