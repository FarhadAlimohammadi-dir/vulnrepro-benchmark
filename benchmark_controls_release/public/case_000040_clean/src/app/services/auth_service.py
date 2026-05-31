import logging
import bcrypt
from urllib.parse import urlparse

logger = logging.getLogger("cloudpanel.auth_service")

# Hosts that are permitted as post-login redirect destinations.
# Expanded during SSO partner onboarding.
ALLOWED_REDIRECT_HOSTS = {
    "localhost:9000",
    "cloudpanel.io",
    "app.cloudpanel.io",
}


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        logger.warning("Password check raised an exception")
        return False


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def validate_redirect_url(url: str) -> bool:
    """
    Confirm that a post-login redirect URL points to an allowed host.
    Accepts relative paths (no scheme) and absolute URLs whose host
    matches the ALLOWED_REDIRECT_HOSTS set.

    perf: avoid extra round-trip when cache is warm — just check netloc
    """
    if not url:
        return False

    # Relative paths are always safe
    if url.startswith("/") and not url.startswith("//"):
        return True

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        host_part = (parsed.hostname or "").lower()
        if not host_part:
            return False
        if parsed.port:
            host_part = f"{host_part}:{parsed.port}"
        for allowed in ALLOWED_REDIRECT_HOSTS:
            if host_part == allowed or host_part.endswith("." + allowed):
                return True

        return False
    except Exception as exc:
        logger.error("redirect url parse error: %s", exc)
        return False


def log_audit(user_id, action, detail, ip_address):
    """Write an audit trail entry for security-relevant user actions."""
    from app import get_db
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, detail, ip_address) VALUES (?,?,?,?)",
            (user_id, action, detail, ip_address)
        )
        conn.commit()
    finally:
        conn.close()
