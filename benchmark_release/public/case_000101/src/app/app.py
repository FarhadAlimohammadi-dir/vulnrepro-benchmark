from flask import Flask, request, jsonify, render_template, session
import os
import json
from datetime import datetime, timedelta
import secrets
import sqlite3
import re

from util import get_request_hash, get_packages_hash
from build import build_firmware, fetch_cached_build
from db import init_db, get_user
from services.audit import log_audit_event
from services.profiles import get_supported_profiles, get_profile_metadata

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = "/app/data/asu.db"
os.makedirs("/app/data", exist_ok=True)

init_db(DB_PATH)

# In-memory session store (production would use Redis)
sessions = {}

# TODO: migrate to Redis for session storage — current approach won't scale horizontally
# TODO: add per-region mirror selection based on user IP geolocation

SEEDED_USERS = [
    {"user_id": 1, "username": "admin", "password": "admin123"},
    {"user_id": 2, "username": "builder", "password": "builder456"},
    {"user_id": 3, "username": "guest", "password": "guest789"},
    {"user_id": 4, "username": "ci_runner", "password": "ci_runner_pass_9x2"},
    {"user_id": 5, "username": "ops_team", "password": "ops_team_2024!"},
    {"user_id": 6, "username": "readonly", "password": "readonly_view_88"},
]

for user in SEEDED_USERS:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, password) VALUES (?, ?, ?)",
              (user["user_id"], user["username"], user["password"]))
    conn.commit()
    conn.close()

# Pre-seed some build history for realistic cache stats
SEED_BUILDS = [
    ("a1b2c3d4e5f6", 1, '{"returncode": 0, "stdout": "Manifest: md5sum=aaa111", "packages_requested": ["curl", "wget"], "profile": "generic", "target": "x86/64", "version": "23.05.0"}', "2024-01-10T08:22:11"),
    ("f6e5d4c3b2a1", 2, '{"returncode": 0, "stdout": "Manifest: md5sum=bbb222", "packages_requested": ["luci", "openvpn"], "profile": "linksys_ea8300", "target": "ipq40xx/generic", "version": "23.05.0"}', "2024-01-11T09:45:00"),
    ("deadbeef1234", 1, '{"returncode": 0, "stdout": "Manifest: md5sum=ccc333", "packages_requested": ["kmod-usb3", "block-mount"], "profile": "generic", "target": "x86/64", "version": "22.03.5"}', "2024-01-12T14:00:00"),
    ("cafebabe5678", 3, '{"returncode": 0, "stdout": "Manifest: md5sum=ddd444", "packages_requested": ["tcpdump", "mtr"], "profile": "tplink_archer-c7-v2", "target": "ath79/generic", "version": "23.05.0"}', "2024-01-13T11:30:22"),
    ("0123456789ab", 4, '{"returncode": 0, "stdout": "Manifest: md5sum=eee555", "packages_requested": ["python3", "python3-pip"], "profile": "generic", "target": "x86/64", "version": "23.05.2"}', "2024-01-14T16:55:01"),
]

for build in SEED_BUILDS:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO builds (cache_key, user_id, result, timestamp) VALUES (?, ?, ?, ?)", build)
    conn.commit()
    conn.close()


@app.route("/", methods=["GET"])
def index():
    """Landing page with build portal overview."""
    return render_template("index.html", title="OpenWrt ASU Build Portal")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for load balancer probes."""
    # TODO: add dependency checks (DB connectivity, disk space, make availability)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM builds")
    build_count = c.fetchone()[0]
    conn.close()
    return jsonify({
        "status": "ok",
        "build_count": build_count,
        "timestamp": datetime.now().isoformat(),
        "version": "2.4.1",
    }), 200


@app.route("/login", methods=["POST"])
def login():
    """Authenticate user and issue session cookie."""
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")

    user = get_user(DB_PATH, username)
    if user and user[2] == password:
        session_id = secrets.token_hex(16)
        sessions[session_id] = {
            "user_id": user[0],
            "username": user[1],
            "expires": datetime.now() + timedelta(hours=24)
        }
        log_audit_event(DB_PATH, user[0], "login", f"user {user[1]} authenticated")
        return jsonify({"status": "ok", "session_id": session_id}), 200

    return jsonify({"error": "invalid credentials"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    """Invalidate an active session."""
    session_id = request.headers.get("X-Session-ID")
    if session_id and session_id in sessions:
        user_id = sessions[session_id]["user_id"]
        del sessions[session_id]
        log_audit_event(DB_PATH, user_id, "logout", "session invalidated")
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "session not found"}), 404


def require_session():
    """Middleware: check valid session."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id or session_id not in sessions:
        return None
    sess = sessions[session_id]
    if sess["expires"] < datetime.now():
        del sessions[session_id]
        return None
    return sess


@app.route("/api/v1/build", methods=["POST"])
def build():
    """
    Accept a firmware build request.
    Checks cache by request hash. If cached, returns cached result.
    Otherwise calls build_firmware() which invokes make manifest.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "invalid JSON"}), 400

    build_request = {
        "target": data.get("target", "x86/64"),
        "version": data.get("version", "23.05.0"),
        "profile": data.get("profile", "generic"),
        "packages": data.get("packages", []),
        "user_id": sess["user_id"],
    }

    # TODO: validate profile against supported device list from remote API
    # TODO: fetch available package index from OpenWrt repo mirror

    cache_key = get_request_hash(build_request)

    cached = fetch_cached_build(DB_PATH, cache_key)
    if cached:
        return jsonify({
            "status": "cached",
            "cache_key": cache_key,
            "result": json.loads(cached[2]),
            "timestamp": cached[3],
        }), 200

    # Build not in cache; invoke build_firmware()
    # Note: build_firmware() performs make manifest invocation with package list expansion
    result = build_firmware(build_request)

    # Store in DB cache
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO builds (cache_key, user_id, result, timestamp) VALUES (?, ?, ?, ?)",
        (cache_key, sess["user_id"], json.dumps(result), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    log_audit_event(DB_PATH, sess["user_id"], "build", f"built {build_request['profile']} for {build_request['target']}")

    return jsonify({
        "status": "built",
        "cache_key": cache_key,
        "result": result,
    }), 200


@app.route("/api/v1/validate-packages", methods=["POST"])
def validate_packages():
    """
    Validates package names against naming conventions before submission.
    Used by the frontend before dispatching build requests.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    packages = data.get("packages", [])

    # Package names: only alphanumeric, dash, underscore, plus-prefix allowed
    safe_pattern = re.compile(r"^[+]?[a-zA-Z0-9_-]+$")

    results = {}
    for pkg in packages:
        results[pkg] = bool(safe_pattern.match(str(pkg)))

    return jsonify({"validation_results": results}), 200


@app.route("/api/v1/cache-stats", methods=["GET"])
def cache_stats():
    """
    Returns aggregate statistics about the firmware build cache.
    Useful for capacity planning and SRE dashboards.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    # TODO: add time-bucketed histogram (hourly, daily, weekly) for telemetry
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM builds")
    total_builds = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT user_id) FROM builds")
    unique_users = c.fetchone()[0]
    c.execute("SELECT timestamp FROM builds ORDER BY timestamp DESC LIMIT 1")
    last_row = c.fetchone()
    conn.close()

    last_build = last_row[0] if last_row else None

    return jsonify({
        "total_cached_builds": total_builds,
        "unique_users": unique_users,
        "last_build_timestamp": last_build,
        "cache_size_mb": round(total_builds * 0.05, 2),
    }), 200


@app.route("/api/v1/build-request-preview", methods=["POST"])
def build_request_preview():
    """
    Preview the cache key for a hypothetical build request without executing it.
    Helps clients avoid duplicate submissions and estimate queue position.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    build_request = {
        "target": data.get("target", "x86/64"),
        "version": data.get("version", "23.05.0"),
        "profile": data.get("profile", "generic"),
        "packages": data.get("packages", []),
    }

    cache_key = get_request_hash(build_request)
    pkg_hash = get_packages_hash(build_request["packages"])

    cached = fetch_cached_build(DB_PATH, cache_key)

    return jsonify({
        "request_cache_key": cache_key,
        "packages_hash": pkg_hash,
        "would_hit_cache": cached is not None,
    }), 200


@app.route("/api/v1/profiles", methods=["GET"])
def list_profiles():
    """
    Returns list of supported hardware profiles for a given target.
    Clients use this to populate the device dropdown in the build UI.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    target = request.args.get("target", "x86/64")
    version = request.args.get("version", "23.05.0")

    # TODO: i18n — profile descriptions are currently English-only
    profiles = get_supported_profiles(target, version)

    return jsonify({
        "target": target,
        "version": version,
        "profiles": profiles,
    }), 200


@app.route("/api/v1/builds/history", methods=["GET"])
def build_history():
    """
    Returns paginated build history for the authenticated user.
    Admins can view all users' history with ?all=true.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    # TODO: implement proper pagination with cursor-based approach for large datasets
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    offset = (page - 1) * per_page

    show_all = request.args.get("all", "false").lower() == "true"
    is_admin = sess["username"] == "admin"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if show_all and is_admin:
        c.execute(
            "SELECT b.id, b.cache_key, b.user_id, u.username, b.timestamp FROM builds b "
            "JOIN users u ON b.user_id = u.user_id "
            "ORDER BY b.timestamp DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
    else:
        c.execute(
            "SELECT b.id, b.cache_key, b.user_id, u.username, b.timestamp FROM builds b "
            "JOIN users u ON b.user_id = u.user_id "
            "WHERE b.user_id = ? ORDER BY b.timestamp DESC LIMIT ? OFFSET ?",
            (sess["user_id"], per_page, offset)
        )

    rows = c.fetchall()
    conn.close()

    history = [
        {"id": r[0], "cache_key": r[1], "user_id": r[2], "username": r[3], "timestamp": r[4]}
        for r in rows
    ]

    return jsonify({"page": page, "per_page": per_page, "history": history}), 200


@app.route("/api/v1/audit-log", methods=["GET"])
def audit_log():
    """
    Returns recent audit events. Restricted to admin users.
    Used by the security operations team for compliance reporting.
    """
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    if sess["username"] != "admin":
        return jsonify({"error": "forbidden"}), 403

    # TODO: add date range filtering for audit exports (GDPR compliance requirement)
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, user_id, action, detail, timestamp FROM audit_log "
        "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    )
    rows = c.fetchall()
    conn.close()

    events = [
        {"id": r[0], "user_id": r[1], "action": r[2], "detail": r[3], "timestamp": r[4]}
        for r in rows
    ]

    return jsonify({"page": page, "per_page": per_page, "events": events}), 200


@app.route("/api/v1/user/profile", methods=["GET"])
def user_profile():
    """Returns the current user's profile details."""
    sess = require_session()
    if not sess:
        return jsonify({"error": "unauthorized"}), 401

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, created_at FROM users WHERE user_id = ?", (sess["user_id"],))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "user not found"}), 404

    return jsonify({
        "user_id": row[0],
        "username": row[1],
        "created_at": row[2],
    }), 200


if __name__ == "__main__":
    # TODO: integrate with real OpenWrt ImageBuilder container
    # TODO: implement request signing and upstream mirror fallback
    # TODO: add per-user build quotas and rate limiting
    # TODO: support hardware-specific firmware variants (ar71xx, ramips, etc)
    app.run(host="0.0.0.0", port=9000, debug=False)