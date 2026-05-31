import logging
from flask import Blueprint, request, jsonify
import flask_login
from app.models import Property
from app.database import get_db

logger = logging.getLogger(__name__)
reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.route("/<int:prop_id>", methods=["GET"])
@flask_login.login_required
def get_report(prop_id):
    prop = Property.get_by_id(prop_id)
    if not prop:
        return jsonify({"error": "Not found"}), 404
    if prop["owner_id"] != flask_login.current_user.id and not flask_login.current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403

    start_date = request.args.get("start", "2024-01-01")
    end_date = request.args.get("end", "2024-12-31")

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT report_date, page_views, bandwidth_gb, cache_hit_ratio, avg_response_ms
               FROM reports
               WHERE property_id=? AND report_date BETWEEN ? AND ?
               ORDER BY report_date DESC
               LIMIT 90""",
            (prop_id, start_date, end_date),
        ).fetchall()
        data = [dict(r) for r in rows]
    finally:
        conn.close()

    totals = {
        "total_views": sum(r["page_views"] for r in data),
        "total_bandwidth_gb": round(sum(r["bandwidth_gb"] for r in data), 2),
        "avg_cache_ratio": round(sum(r["cache_hit_ratio"] for r in data) / max(len(data), 1), 4),
        "avg_response_ms": round(sum(r["avg_response_ms"] for r in data) / max(len(data), 1), 1),
    }
    return jsonify({"property_id": prop_id, "totals": totals, "daily": data}), 200


@reports_bp.route("/summary", methods=["GET"])
@flask_login.login_required
def get_summary():
    user_id = flask_login.current_user.id
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT p.name, p.domain, SUM(r.page_views) as total_views,
                      SUM(r.bandwidth_gb) as total_bw
               FROM properties p
               LEFT JOIN reports r ON p.id = r.property_id
               WHERE p.owner_id=?
               GROUP BY p.id
               ORDER BY total_views DESC""",
            (user_id,),
        ).fetchall()
        return jsonify({"summary": [dict(r) for r in rows]}), 200
    finally:
        conn.close()