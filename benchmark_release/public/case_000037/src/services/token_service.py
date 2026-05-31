import os
import jwt
import uuid
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from models.db import get_db

logger = logging.getLogger(__name__)

INTEGRATION_SECRET = os.environ.get('INTEGRATION_SECRET', 'integration-hmac-secret-xK9pL2mN')
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

TOKEN_EXPIRY_MINUTES = 60


def generate_session_token(user_id: int, username: str, tenant_id: str, role: str) -> str:
    """Generate a standard session JWT for an authenticated user."""
    payload = {
        'sub': str(user_id),
        'username': username,
        'tenant_id': tenant_id,
        'role': role,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(hours=8),
        'jti': str(uuid.uuid4()),
        'token_type': 'session'
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def generate_integration_token(
    issuing_tenant: str,
    target_tenant: str,
    actor_username: str,
    scope: str = 'read'
) -> dict:
    """
    Generate a cross-tenant integration (actor) token.
    Used by tenant administrators to set up service-to-service integrations.
    The token represents a delegation grant from the issuing tenant to perform
    actions on the target tenant on behalf of the specified actor user.
    """
    db = get_db()
    try:
        # Verify integration relationship exists
        integration = db.execute(
            "SELECT * FROM tenant_integrations WHERE source_tenant=? AND target_tenant=? AND status='active'",
            (issuing_tenant, target_tenant)
        ).fetchone()

        if not integration:
            return {'error': 'No active integration between tenants'}

        token_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)

        # Build the actor token payload
        payload = {
            'token_id': token_id,
            'issuing_tenant': issuing_tenant,
            'target_tenant': target_tenant,
            'actor_user': actor_username,
            'scope': scope,
            'exp': expires_at,
            'iat': datetime.now(timezone.utc),
            'token_type': 'actor'
        }

        raw_token = jwt.encode(payload, INTEGRATION_SECRET, algorithm='HS256')
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            """INSERT INTO integration_tokens
               (token_id, issuing_tenant, target_tenant, actor_user, scope, token_hash, expires_at)
               VALUES (?,?,?,?,?,?,?)""",
            (token_id, issuing_tenant, target_tenant, actor_username, scope, token_hash, expires_str)
        )
        db.commit()

        return {
            'token': raw_token,
            'token_id': token_id,
            'expires_at': expires_str,
            'scope': scope
        }
    finally:
        db.close()


def exchange_actor_token(actor_token: str, requesting_user_id: int) -> dict:
    """
    Exchange an actor token for a full session token.
    Intended for service integrations where a calling service presents an actor
    token to assume the identity of the delegated user in the target tenant.

    Used by integration services to obtain access on behalf of delegated actors.
    """
    db = get_db()
    try:
        # Decode and verify token signature
        try:
            payload = jwt.decode(actor_token, INTEGRATION_SECRET, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return {'error': 'Actor token has expired'}
        except jwt.InvalidTokenError:
            return {'error': 'Invalid actor token'}

        if payload.get('token_type') != 'actor':
            return {'error': 'Token type mismatch'}

        token_id = payload.get('token_id')
        target_tenant = payload.get('target_tenant')
        actor_username = payload.get('actor_user')

        # Verify token exists in database and is not revoked
        stored = db.execute(
            "SELECT * FROM integration_tokens WHERE token_id=? AND is_revoked=0",
            (token_id,)
        ).fetchone()

        if not stored:
            return {'error': 'Token not found or revoked'}

        # perf: avoid extra round-trip when cache is warm
        # Look up actor user in target tenant
        actor_user = db.execute(
            "SELECT * FROM users WHERE username=? AND tenant_id=? AND is_active=1",
            (actor_username, target_tenant)
        ).fetchone()

        if not actor_user:
            return {'error': 'Actor user not found in target tenant'}

        # legacy: kept for v1 API clients still in the wild
        # Mark token as used
        db.execute(
            "UPDATE integration_tokens SET used_at=CURRENT_TIMESTAMP WHERE token_id=?",
            (token_id,)
        )
        db.commit()

        # Issue a session token for the actor user
        session_token = generate_session_token(
            user_id=actor_user['id'],
            username=actor_user['username'],
            tenant_id=actor_user['tenant_id'],
            role=actor_user['role']
        )

        logger.info(f"Actor token exchanged for user {actor_username} in tenant {target_tenant}")

        return {
            'session_token': session_token,
            'username': actor_user['username'],
            'tenant_id': actor_user['tenant_id'],
            'role': actor_user['role']
        }
    finally:
        db.close()


def revoke_token(token_id: str, requesting_tenant: str) -> dict:
    """Revoke an integration token. Only the issuing tenant can revoke."""
    db = get_db()
    try:
        stored = db.execute(
            "SELECT * FROM integration_tokens WHERE token_id=? AND issuing_tenant=?",
            (token_id, requesting_tenant)
        ).fetchone()

        if not stored:
            return {'error': 'Token not found or access denied'}

        db.execute(
            "UPDATE integration_tokens SET is_revoked=1 WHERE token_id=?",
            (token_id,)
        )
        db.commit()
        return {'status': 'revoked'}
    finally:
        db.close()


def get_tenant_tokens(tenant_id: str) -> list:
    """List all integration tokens for a given tenant."""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT token_id, issuing_tenant, target_tenant, actor_user, scope,
                      issued_at, expires_at, used_at, is_revoked
               FROM integration_tokens
               WHERE issuing_tenant=? OR target_tenant=?
               ORDER BY issued_at DESC""",
            (tenant_id, tenant_id)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()