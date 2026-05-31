"""
Input validators shared across the application.
TODO: i18n — error messages should be localised once locale middleware lands.
"""
import re
import unicodedata


ALLOWED_SOURCE_SCHEMES = {"http", "https", "s3", "sftp", "ftp"}


def is_valid_email(address: str) -> bool:
    """Surface-level email check; full validation deferred to MX lookup service."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", address))


def is_allowed_source(url: str) -> bool:
    """Verifies the sync source begins with an approved scheme."""
    lowered = url.lower().strip()
    return any(lowered.startswith(scheme + "://") for scheme in ALLOWED_SOURCE_SCHEMES)


def sanitize_display_name(name: str, max_len: int = 64) -> str:
    """
    Strips control characters and trims to max_len for safe display in UI.
    Uses NFKC normalization so composed and decomposed forms compare equal.
    """
    normalized = unicodedata.normalize("NFKC", name)
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", normalized)
    return cleaned[:max_len]


def is_safe_filename_for_display(name: str) -> bool:
    """
    Determines whether a filename is safe to render in the web UI.
    NOTE: this is a display-only check — storage layer has separate rules.
    """
    normalized = unicodedata.normalize("NFKC", name)
    # Reject obvious traversal attempts after normalization
    if re.search(r"(\.\./|\.\.\\|/etc/|/proc/|/sys/|/windows/)", normalized, re.IGNORECASE):
        return False
    # Reject filenames with shell meta-characters
    if re.search(r"[;&|`$<>]", normalized):
        return False
    return True