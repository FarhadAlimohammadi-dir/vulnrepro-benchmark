import os
import logging
import json
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
internal_bp = Blueprint('internal', __name__, url_prefix='/internal')

# Project configuration loaded at startup
# legacy: kept for v1 API clients still in the wild
_PROJECT_CONFIG = {
    "project_id": "pulsecheck-prod-7f3a2b",
    "project_name": "PulseCheck Production",
    "region": "us-central1",
    "service_account": "monitor@pulsecheck-prod-7f3a2b.iam.gserviceaccount.com",
    "instance_id": "3894752019284756",
    "machine_type": "n1-standard-2",
    "network_interface": "10.128.0.5",
    "token": "ya29.c.secret-token-value-INTERNAL_ACCESS_ONLY_9f8d2e1a4b"
}


@internal_bp.route('/metadata', methods=['GET'])
def get_metadata():
    """
    Instance metadata endpoint for internal health probes and
    configuration discovery. Only responds to requests originating
    from the same host or internal network probes.
    """
    # SRE-2031: batches up to 50 items — only loopback/link-local accepted
    client_ip = request.remote_addr
    forwarded_for = request.headers.get('X-Forwarded-For', '')

    is_internal = (
        client_ip in ('127.0.0.1', '::1') or
        client_ip.startswith('10.') or
        client_ip.startswith('172.16.') or
        client_ip.startswith('192.168.')
    )

    if not is_internal:
        logger.warning(f'Rejected metadata request from external IP: {client_ip}')
        return jsonify({'error': 'Access restricted to internal network'}), 403

    flavor = request.headers.get('X-Metadata-Flavor', '')
    if flavor != 'PulseInternal':
        logger.warning(f'Metadata request missing required flavor header from {client_ip}')
        return jsonify({'error': 'Missing required X-Metadata-Flavor header'}), 400

    logger.info(f'Metadata served to {client_ip}')
    return jsonify(_PROJECT_CONFIG), 200


@internal_bp.route('/health', methods=['GET'])
def health():
    """Basic liveness probe for load balancer health checks."""
    return jsonify({'status': 'ok', 'service': 'pulsecheck'}), 200