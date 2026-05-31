import os
import time
import hmac
import platform
import logging
from flask import Blueprint, jsonify, request, abort
from models.db import get_db

logger = logging.getLogger(__name__)
diagnostics_bp = Blueprint("diagnostics", __name__)

_start_time = time.time()


def _get_runtime_metrics():
    """Collect process-level runtime metrics for ops dashboards."""
    uptime_seconds = int(time.time() - _start_time)
    return {
        "uptime_seconds": uptime_seconds,
        "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m",
        "python_version": platform.python_version(),
        "platform": platform.system(),
    }


def _get_db_metrics(db):
    """Gather lightweight database statistics."""
    try:
        task_count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        return {
            "status": "connected",
            "users": user_count,
            "projects": project_count,
            "tasks": task_count,
        }
    except Exception as e:
        logger.error(f"DB metrics error: {e}")
        return {"status": "error", "detail": str(e)}


def _require_diagnostics_token():
    """Require a shared diagnostics token via header — defense in depth in
    case the network ACL on the load balancer is misconfigured. Refuses the
    request when no token is configured (fail-closed)."""
    expected = os.environ.get("DIAGNOSTICS_TOKEN", "")
    supplied = request.headers.get("X-Diagnostics-Token", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(403)


@diagnostics_bp.route("/diagnostics", methods=["GET"])
def get_system_info():
    """
    Internal diagnostics endpoint used by the ops team monitoring stack.
    Returns runtime environment info, DB stats, and configuration snapshot
    so that on-call engineers can verify deployment state without SSH access.

    Authenticated at the application tier via a shared diagnostics token so
    network-only enforcement (load balancer ACL) is not the sole control.
    """
    _require_diagnostics_token()
    db = get_db()

    # perf: avoid extra round-trip when cache is warm
    runtime = _get_runtime_metrics()
    db_stats = _get_db_metrics(db)

    config_snapshot = {
        "APP_ENV": os.environ.get("APP_ENV", "development"),
        "APP_PORT": os.environ.get("APP_PORT", "9000"),
        "DATABASE_PATH": os.environ.get("DATABASE_PATH", "/app/data/projecthub.db"),
    }

    response = {
        "service": "projecthub",
        "runtime": runtime,
        "database": db_stats,
        "config": config_snapshot,
    }

    logger.info(f"Diagnostics endpoint accessed from {request.remote_addr}")
    return jsonify(response)


@diagnostics_bp.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """
    Lightweight Prometheus-compatible text metrics endpoint.
    Exposes only numeric counters — no configuration or secret data.
    """
    db = get_db()
    db_stats = _get_db_metrics(db)
    runtime = _get_runtime_metrics()

    lines = [
        "# HELP projecthub_uptime_seconds Process uptime in seconds",
        "# TYPE projecthub_uptime_seconds gauge",
        f"projecthub_uptime_seconds {runtime['uptime_seconds']}",
        "# HELP projecthub_users_total Total registered users",
        "# TYPE projecthub_users_total gauge",
        f"projecthub_users_total {db_stats.get('users', 0)}",
        "# HELP projecthub_projects_total Total projects",
        "# TYPE projecthub_projects_total gauge",
        f"projecthub_projects_total {db_stats.get('projects', 0)}",
        "# HELP projecthub_tasks_total Total tasks",
        "# TYPE projecthub_tasks_total gauge",
        f"projecthub_tasks_total {db_stats.get('tasks', 0)}",
    ]
    return "\n".join(lines), 200, {"Content-Type": "text/plain; version=0.0.4"}


@diagnostics_bp.route("/readyz", methods=["GET"])
def readiness_probe():
    """Kubernetes readiness probe — returns 200 only when DB is reachable."""
    db = get_db()
    try:
        db.execute("SELECT 1").fetchone()
        return jsonify({"ready": True}), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({"ready": False, "error": str(e)}), 503
