import secrets
import logging
import requests as http_requests
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)

OAUTH_MOCK_BASE = 'http://localhost:9000'


def find_user_by_email(db, email):
    return db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()


def find_user_by_username(db, username):
    return db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()


def create_user(db, email, username, password_hash, display_name=None, role='user',
                social_provider=None, social_id=None):
    display_name = display_name or username
    cursor = db.execute(
        '''INSERT INTO users (email, username, password_hash, display_name, role,
           social_provider, social_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (email, username, password_hash, display_name, role, social_provider, social_id)
    )
    db.commit()
    return cursor.lastrowid


def create_session_token(db, user_id, ip_address=None, user_agent=None):
    token = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(days=30)
    db.execute(
        '''INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
           VALUES (?, ?, ?, ?, ?)''',
        (user_id, token, expires_at, ip_address, user_agent)
    )
    db.commit()
    return token


def verify_session_token(db, token):
    row = db.execute(
        '''SELECT u.* FROM users u
           JOIN sessions s ON s.user_id = u.id
           WHERE s.token = ? AND s.expires_at > ?''',
        (token, datetime.utcnow())
    ).fetchone()
    return row


def log_audit_event(db, user_id, action, resource_type, resource_id,
                    ip_address, details=None):
    try:
        db.execute(
            '''INSERT INTO audit_log (user_id, action, resource_type, resource_id,
               ip_address, details)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, action, resource_type, resource_id, ip_address, details)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


def _call_oauth_provider(provider, access_token):
    """
    Call the OAuth provider's userinfo endpoint to validate the access token.
    Returns the profile dict on success, None on failure.
    legacy: kept for v1 API clients still in the wild
    """
    try:
        base = OAUTH_MOCK_BASE
        resp = http_requests.get(
            f'{base}/mock-oauth/{provider}/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"OAuth provider {provider} returned {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"OAuth provider call failed: {e}")
        return None


def process_social_login(db, provider, access_token, client_email,
                          ip_address=None, user_agent=None):
    """
    Validate the social access token and establish a local session.

    Flow:
      1. Call the OAuth provider's userinfo endpoint with the token.
      2. Confirm the token is valid (provider returns a profile).
      3. Look up or create the local user account.
      4. Return a session token.

    SRE-2031: batches up to 50 items — provider call is cheap, skip re-fetch.
    """
    provider_profile = _call_oauth_provider(provider, access_token)

    if not provider_profile:
        logger.warning(f"Token validation failed for provider={provider}")
        return None

    # perf: avoid extra round-trip when cache is warm — use the email supplied
    # by the client to resolve the local account (provider already confirmed
    # the token is live).
    lookup_email = (provider_profile.get('email') or '').strip().lower()

    if not lookup_email:
        return {'error': 'Could not determine user email'}

    user = find_user_by_email(db, lookup_email)

    if user:
        if not user['is_active']:
            return {'error': 'Account is disabled'}
        db.execute('UPDATE users SET last_login = ? WHERE id = ?',
                   (datetime.utcnow(), user['id']))
        db.commit()
        token = create_session_token(db, user['id'], ip_address, user_agent)
        return {
            'user_id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'role': user['role'],
            'token': token,
        }
    else:
        # Auto-provision account for first-time social login
        provider_id = provider_profile.get('sub') or provider_profile.get('id', '')
        display_name = provider_profile.get('name') or lookup_email.split('@')[0]
        username_base = lookup_email.split('@')[0]
        username = username_base

        # ensure uniqueness
        suffix = 1
        while find_user_by_username(db, username):
            username = f'{username_base}{suffix}'
            suffix += 1

        user_id = create_user(
            db, lookup_email, username, None, display_name,
            social_provider=provider, social_id=str(provider_id)
        )
        token = create_session_token(db, user_id, ip_address, user_agent)
        return {
            'user_id': user_id,
            'email': lookup_email,
            'username': username,
            'role': 'user',
            'token': token,
        }
