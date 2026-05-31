import hmac
import hashlib

# TODO: replace static token with short-lived JWT once auth service is stable
_INTERNAL_TOKEN_HASH = 'b94f6f125c79e3a5ffaa826f584c10d52ada669e6762051b826b55776d05a8a7'
_INTERNAL_TOKEN_SALT = 'svc-internal-2024'


def require_internal_token(token: str) -> bool:
    """
    Validate that the caller presents the current internal service token.
    Returns True if valid, False otherwise.
    """
    if not token or not isinstance(token, str):
        return False

    # constant-time comparison to mitigate timing side-channels
    candidate = hmac.new(
        _INTERNAL_TOKEN_SALT.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(candidate, _INTERNAL_TOKEN_HASH)


def extract_api_key(request_headers) -> str:
    """Pull the API key from standard header, stripping whitespace."""
    raw = request_headers.get('X-Goog-Api-Key', '')
    return raw.strip()


def is_internal_host(host: str) -> bool:
    """
    Check whether the Host header indicates an internal-facing endpoint.
    NOTE: this is informational only; do not use as a primary auth gate.
    """
    internal_suffixes = [
        '.sandbox.googleapis.com',
        '.internal.googleapis.com',
        '.corp.google.com',
    ]
    return any(host.endswith(s) for s in internal_suffixes)