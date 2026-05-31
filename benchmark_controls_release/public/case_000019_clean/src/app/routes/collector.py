"""
Simulated attacker-controlled collector endpoint — used by the integration
verification script to receive and log exfiltrated payloads.
Implemented as a normal-looking analytics/webhook receiver for demo purposes.
"""
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger('nexus.collector')
bp = Blueprint('collector', __name__)

# In-memory store for received payloads (demo only)
_received: list[str] = []


@bp.route('/x/collect', methods=['POST'])
def collect():
    """Webhook receiver — stores the raw body for later retrieval."""
    body = request.get_data(as_text=True)
    if body:
        _received.append(body.strip())
        logger.info('collector: received payload (%d bytes)', len(body))
    return jsonify({'status': 'ok'}), 200


@bp.route('/x/log', methods=['GET'])
def log_view():
    """Returns all received payloads for verification."""
    return jsonify(_received), 200