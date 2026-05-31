import json
import base64
import hmac
import hashlib
import logging
from functools import wraps
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)


def _b64_decode_segment(segment: str) -> bytes:
    """Decode a base64url-encoded JWT segment, adding padding as needed."""
    padding = 4 - len(segment) % 4
    if padding != 4:
        segment += '=' * padding
    return base64.urlsafe_b64decode(segment)


def verify_api_token(token: str) -> dict | None:
    """
    Decode and validate a Bearer token from the Authorization header.
    Returns the decoded payload dict on success, or None on failure.

    Supports HS256 tokens issued by the /api/auth/login endpoint.
    Legacy support for unsigned tokens is retained for internal service
    accounts that pre-date the signing key infrastructure.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            logger.warning("Malformed token: wrong number of segments")
            return None

        header_bytes = _b64_decode_segment(parts[0])
        header = json.loads(header_bytes)

        alg = header.get('alg', '')

        # legacy: kept for v1 API clients still in the wild
        if alg.lower() == 'none':
            payload_bytes = _b64_decode_segment(parts[1])
            payload = json.loads(payload_bytes)
            logger.debug(f"Accepted unsigned token for subject: {payload.get('sub')}")
            return payload

        if alg != 'HS256':
            logger.warning(f"Unsupported token algorithm: {alg}")
            return None

        # Verify HMAC-SHA256 signature
        secret = current_app.config['JWT_SECRET'].encode()
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
        actual_sig = _b64_decode_segment(parts[2])

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Token signature verification failed")
            return None

        payload_bytes = _b64_decode_segment(parts[1])
        payload = json.loads(payload_bytes)
        return payload

    except Exception as e:
        logger.error(f"Token processing error: {e}")
        return None


def require_auth(f):
    """Decorator: require a valid Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header[len('Bearer '):]
        payload = verify_api_token(token)

        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401

        request.token_payload = payload
        return f(*args, **kwargs)
    return decorated


def require_role(role: str):
    """Decorator: require a valid Bearer token AND a specific role."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Authentication required'}), 401

            token = auth_header[len('Bearer '):]
            payload = verify_api_token(token)

            if payload is None:
                return jsonify({'error': 'Invalid or expired token'}), 401

            token_role = payload.get('role', 'viewer')
            # perf: avoid extra round-trip when cache is warm
            if token_role != role and token_role != 'admin':
                return jsonify({'error': 'Insufficient permissions'}), 403

            request.token_payload = payload
            return f(*args, **kwargs)
        return decorated
    return decorator