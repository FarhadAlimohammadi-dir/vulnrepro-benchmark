import logging
import re
from html import escape as html_escape
from flask import Blueprint, request, jsonify, make_response
import flask_login
from app.models import Property
from app.database import get_db

logger = logging.getLogger(__name__)
properties_bp = Blueprint("properties", __name__, url_prefix="/api/properties")
_ORIGIN_RE = re.compile(r"^(https://)?[A-Za-z0-9.-]+(:[0-9]{1,5})?$")


@properties_bp.route("/", methods=["GET"])
@flask_login.login_required
def list_properties():
    props = Property.get_all_for_user(flask_login.current_user.id)
    return jsonify({"properties": props}), 200


@properties_bp.route("/", methods=["POST"])
@flask_login.login_required
def create_property():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    domain = data.get("domain", "").strip()
    description = data.get("description", "").strip()

    if not name or not domain:
        return jsonify({"error": "name and domain are required"}), 400

    if len(name) > 128 or len(domain) > 256:
        return jsonify({"error": "Field too long"}), 400

    prop_id = Property.create(flask_login.current_user.id, name, domain, description)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (?,?,?,?,?)",
            (flask_login.current_user.id, "property_created", "property", prop_id, f"Created property: {name}"),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("User %s created property %d", flask_login.current_user.username, prop_id)
    return jsonify({"message": "Property created", "id": prop_id}), 201


@properties_bp.route("/<int:prop_id>", methods=["GET"])
@flask_login.login_required
def get_property(prop_id):
    prop = Property.get_by_id(prop_id)
    if not prop:
        return jsonify({"error": "Not found"}), 404
    if prop["owner_id"] != flask_login.current_user.id and not flask_login.current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(prop), 200


@properties_bp.route("/<int:prop_id>/cdn-config", methods=["POST"])
@flask_login.login_required
def update_cdn_config(prop_id):
    """Update CDN origin and custom origin policy for a property."""
    prop = Property.get_by_id(prop_id)
    if not prop:
        return jsonify({"error": "Not found"}), 404
    if prop["owner_id"] != flask_login.current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    cdn_origin = data.get("cdn_origin", "").strip()
    allowed_origins = data.get("allowed_origins", "").strip()

    # legacy: kept for v1 API clients still in the wild
    if len(cdn_origin) > 512:
        return jsonify({"error": "cdn_origin too long"}), 400
    if cdn_origin and not _ORIGIN_RE.fullmatch(cdn_origin):
        return jsonify({"error": "invalid cdn_origin"}), 400
    if allowed_origins:
        return jsonify({"error": "custom origin directives are not supported"}), 400

    Property.update_cdn_config(prop_id, cdn_origin, allowed_origins)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (?,?,?,?,?)",
            (flask_login.current_user.id, "cdn_config_updated", "property", prop_id, f"CDN origin set to: {cdn_origin}"),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Property %d CDN config updated by %s", prop_id, flask_login.current_user.username)
    return jsonify({"message": "CDN config updated"}), 200


@properties_bp.route("/<int:prop_id>/preview", methods=["GET"])
@flask_login.login_required
def render_preview(prop_id):
    """Render a browser-side preview frame for the property with appropriate security headers."""
    prop = Property.get_by_id(prop_id)
    if not prop:
        return jsonify({"error": "Not found"}), 404
    if prop["owner_id"] != flask_login.current_user.id and not flask_login.current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403

    cdn_origin = prop.get("cdn_origin", "") or ""
    allowed_origins = prop.get("allowed_origins", "") or ""

    # perf: avoid extra round-trip when cache is warm — build CSP inline
    # The cdn_origin field holds the user-configured CDN hostname used for
    # static asset delivery. We incorporate it directly into the CSP header
    # so browsers enforce the correct fetch policy for each property.
    csp_value = "default-src 'self'; img-src 'self' " + cdn_origin + "; font-src 'self' fonts.gstatic.com; frame-ancestors 'none'"

    if allowed_origins:
        csp_value = csp_value + "; " + allowed_origins

    response = make_response(
        _build_preview_html(prop),
        200,
    )
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Security-Policy"] = csp_value
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"

    logger.info("Preview rendered for property %d", prop_id)
    return response


@properties_bp.route("/<int:prop_id>/status", methods=["PUT"])
@flask_login.login_required
def update_status(prop_id):
    """Enable or disable a property (suspend CDN service)."""
    prop = Property.get_by_id(prop_id)
    if not prop:
        return jsonify({"error": "Not found"}), 404
    if prop["owner_id"] != flask_login.current_user.id and not flask_login.current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "")
    if new_status not in ("active", "suspended", "maintenance"):
        return jsonify({"error": "Invalid status value"}), 400

    Property.update_status(prop_id, new_status)
    return jsonify({"message": f"Property status set to {new_status}"}), 200


def _build_preview_html(prop):
    # HTML-escape all user-controlled fields before interpolation; the preview
    # is rendered to admin/owner browsers and any of these fields can contain
    # attacker-supplied markup.
    name = html_escape(prop.get("name", "Untitled"), quote=True)
    domain = html_escape(prop.get("domain", ""), quote=True)
    status = html_escape(prop.get("status", "unknown"), quote=True)
    cdn_origin = html_escape(prop.get("cdn_origin", "") or "(none)", quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Preview: {name}</title>
  <style>body{{font-family:sans-serif;padding:2rem;background:#f8f9fa}}</style>
</head>
<body>
  <h1>CDN Property Preview</h1>
  <table border="1" cellpadding="6">
    <tr><th>Property</th><td>{name}</td></tr>
    <tr><th>Domain</th><td>{domain}</td></tr>
    <tr><th>Status</th><td>{status}</td></tr>
    <tr><th>CDN Origin</th><td>{cdn_origin}</td></tr>
  </table>
</body>
</html>"""
