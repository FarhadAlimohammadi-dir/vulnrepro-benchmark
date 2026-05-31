"""
Mock OAuth provider — simulates Google/Facebook userinfo endpoints for
local development and integration testing.
"""
import logging
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)
oauth_provider_bp = Blueprint('oauth_provider', __name__)


def get_db():
    return current_app.config['get_db']()


@oauth_provider_bp.route('/<provider>/userinfo', methods=['GET'])
def userinfo(provider):
    """
    Mock OAuth userinfo endpoint.
    Validates a Bearer token and returns the associated profile.
    In production this would be: https://openidconnect.googleapis.com/v1/userinfo
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing bearer token'}), 401

    token = auth_header[7:].strip()
    if not token:
        return jsonify({'error': 'Empty token'}), 401

    db = get_db()
    row = db.execute(
        'SELECT * FROM oauth_tokens WHERE token = ? AND provider = ?',
        (token, provider)
    ).fetchone()

    if not row:
        logger.warning(f"Invalid token for provider={provider}: {token[:20]}...")
        return jsonify({'error': 'Invalid or expired token'}), 401

    # Return the profile associated with THIS token's actual owner
    return jsonify({
        'sub': f'{provider}|{row["id"]}',
        'email': row['user_email'],
        'email_verified': True,
        'name': row['user_email'].split('@')[0].title(),
        'provider': provider,
        'app_id': row['app_id'],
    }), 200


@oauth_provider_bp.route('/<provider>/token', methods=['POST'])
def exchange_token(provider):
    """
    Mock token exchange endpoint — converts an authorization code to an access token.
    In production: https://oauth2.googleapis.com/token
    """
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    redirect_uri = data.get('redirect_uri', '')

    if not code or not redirect_uri:
        return jsonify({'error': 'code and redirect_uri are required'}), 400

    db = get_db()
    # For testing: code == email prefix maps to a token
    row = db.execute(
        'SELECT * FROM oauth_tokens WHERE provider = ? LIMIT 1',
        (provider,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'No tokens available for provider'}), 400

    return jsonify({
        'access_token': row['token'],
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': 'openid email profile',
    }), 200