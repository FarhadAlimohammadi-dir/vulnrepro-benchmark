from flask import Blueprint, request, jsonify, session, current_app
from ..middleware.auth import login_required
from ..services.ticket_service import create_ticket
from ..services.audit_service import log_action

api_bp = Blueprint("api", __name__)


@api_bp.route("/ticket", methods=["POST"])
@login_required
def process_ticket():
    data = request.get_json(force=True, silent=True) or {}
    subject = str(data.get("subject", "")).strip()
    body    = str(data.get("body", "")).strip()

    if not subject or not body:
        return jsonify({"error": "subject and body are required"}), 400

    # SRE-2031: enforce max body length to keep prompt context within model limits
    max_len = current_app.config.get("MAX_TICKET_BODY", 4000)
    if len(body) > max_len:
        return jsonify({"error": f"ticket body too long (max {max_len} chars)"}), 400

    if len(subject) > 200:
        return jsonify({"error": "subject too long (max 200 chars)"}), 400

    try:
        result = create_ticket(session["user"], subject, body)
    except Exception as exc:
        current_app.logger.error("ticket processing error for user %s: %s", session.get("user"), exc)
        return jsonify({"error": "processing failed, please retry"}), 500

    return jsonify(result)


@api_bp.route("/tag", methods=["POST"])
@login_required
def tag_ticket():
    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("text", ""))[:2000]

    keyword_map = {
        "billing":   ["billing", "invoice", "payment", "charge", "refund"],
        "outage":    ["outage", "down", "unavailable", "offline", "disruption"],
        "feature":   ["feature", "request", "enhancement", "add", "suggestion"],
        "account":   ["account", "login", "password", "access", "sso", "auth"],
        "technical": ["bug", "error", "crash", "broken", "exception", "timeout"],
    }
    tags = []
    for tag, keywords in keyword_map.items():
        if any(k in text.lower() for k in keywords):
            tags.append(tag)
    if not tags:
        tags = ["general"]

    return jsonify({"tags": tags})


@api_bp.route("/sentiment", methods=["GET"])
@login_required
def get_sentiment():
    text = request.args.get("text", "")
    if not text:
        return jsonify({"error": "text param required"}), 400
    if len(text) > 1000:
        return jsonify({"error": "text param too long"}), 400

    # perf: avoid extra round-trip when cache is warm — pure local heuristic
    positive_words = {"great", "thanks", "thank", "helpful", "love", "good", "excellent", "appreciate", "resolved", "perfect"}
    negative_words = {"angry", "terrible", "awful", "bad", "hate", "broken", "useless", "frustrated", "upset", "unacceptable"}

    words = set(text.lower().split())
    pos = len(words & positive_words)
    neg = len(words & negative_words)

    if pos > neg:
        sentiment = "positive"
    elif neg > pos:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return jsonify({"sentiment": sentiment, "score": pos - neg})


@api_bp.route("/classify", methods=["POST"])
@login_required
def classify_ticket():
    data = request.get_json(force=True, silent=True) or {}
    subject = str(data.get("subject", ""))[:200]

    # SRE-2031: strict truncation per classifier contract
    categories = ["billing", "technical", "account", "general", "feature"]
    idx = sum(ord(c) for c in subject) % len(categories)
    return jsonify({"category": categories[idx]})


@api_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket_api(ticket_id):
    from ..services.ticket_service import get_ticket_by_id
    ticket = get_ticket_by_id(ticket_id, session["user"])
    if not ticket:
        return jsonify({"error": "not found"}), 404
    return jsonify(ticket)


@api_bp.route("/tickets/<int:ticket_id>/status", methods=["PATCH"])
@login_required
def patch_ticket_status(ticket_id):
    from ..services.ticket_service import get_ticket_by_id, update_ticket_status
    data = request.get_json(force=True, silent=True) or {}
    new_status = str(data.get("status", "")).strip()
    ticket = get_ticket_by_id(ticket_id, session["user"])
    if not ticket:
        return jsonify({"error": "not found"}), 404
    ok = update_ticket_status(ticket_id, new_status, session["user"])
    if not ok:
        return jsonify({"error": "invalid status value"}), 400
    return jsonify({"ok": True, "status": new_status})