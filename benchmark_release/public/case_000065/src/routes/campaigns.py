import logging
from flask import Blueprint, request, jsonify, session
import database

logger = logging.getLogger(__name__)
campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/api/campaigns')


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Authentication required"}), 401
    return None


@campaigns_bp.route('', methods=['GET'])
def list_campaigns():
    err = _require_auth()
    if err:
        return err

    user_id = session['user_id']
    role = session.get('role', 'analyst')

    if role == 'admin':
        campaigns = database.query_db(
            """SELECT c.*, u.username as owner_name
               FROM campaigns c JOIN users u ON c.owner_id = u.id
               ORDER BY c.created_at DESC"""
        )
    else:
        campaigns = database.query_db(
            """SELECT c.*, u.username as owner_name
               FROM campaigns c JOIN users u ON c.owner_id = u.id
               WHERE c.owner_id = ?
               ORDER BY c.created_at DESC""",
            (user_id,)
        )

    return jsonify([dict(c) for c in campaigns])


@campaigns_bp.route('', methods=['POST'])
def create_campaign():
    err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    utm_source = data.get('utm_source', '').strip()
    utm_medium = data.get('utm_medium', '').strip()
    utm_campaign = data.get('utm_campaign', '').strip()
    budget = data.get('budget', 0)

    if not name:
        return jsonify({"error": "Campaign name required"}), 400

    if not isinstance(budget, (int, float)) or budget < 0:
        return jsonify({"error": "Invalid budget value"}), 400

    # Validate UTM parameters contain only safe characters
    import re
    utm_pattern = re.compile(r'^[a-zA-Z0-9_\-\.]*$')
    for field, value in [('utm_source', utm_source), ('utm_medium', utm_medium),
                          ('utm_campaign', utm_campaign)]:
        if value and not utm_pattern.match(value):
            return jsonify({"error": f"Invalid characters in {field}"}), 400

    cid = database.execute_db(
        """INSERT INTO campaigns
           (owner_id, name, utm_source, utm_medium, utm_campaign, budget, status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')""",
        (session['user_id'], name, utm_source, utm_medium, utm_campaign, budget)
    )

    database.execute_db(
        "INSERT INTO audit_log (user_id, action, resource, details, ip_address) VALUES (?, ?, ?, ?, ?)",
        (session['user_id'], 'create_campaign', f'campaign:{cid}', name, request.remote_addr)
    )

    return jsonify({"message": "Campaign created", "campaign_id": cid}), 201


@campaigns_bp.route('/<int:campaign_id>', methods=['PUT'])
def update_campaign(campaign_id):
    err = _require_auth()
    if err:
        return err

    user_id = session['user_id']
    role = session.get('role', 'analyst')

    campaign = database.query_db(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True
    )
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if role != 'admin' and campaign['owner_id'] != user_id:
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    allowed_fields = ['name', 'utm_source', 'utm_medium', 'utm_campaign', 'budget', 'status']
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [campaign_id]
    database.execute_db(f"UPDATE campaigns SET {set_clause} WHERE id = ?", values)

    database.execute_db(
        "INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, 'update_campaign', f'campaign:{campaign_id}', request.remote_addr)
    )

    return jsonify({"message": "Campaign updated"})


@campaigns_bp.route('/<int:campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    err = _require_auth()
    if err:
        return err

    user_id = session['user_id']
    role = session.get('role', 'analyst')

    campaign = database.query_db(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True
    )
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if role != 'admin' and campaign['owner_id'] != user_id:
        return jsonify({"error": "Access denied"}), 403

    database.execute_db("DELETE FROM campaigns WHERE id = ?", (campaign_id,))

    database.execute_db(
        "INSERT INTO audit_log (user_id, action, resource, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, 'delete_campaign', f'campaign:{campaign_id}', request.remote_addr)
    )

    return jsonify({"message": "Campaign deleted"})