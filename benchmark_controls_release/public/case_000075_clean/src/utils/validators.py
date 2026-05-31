import re

# NOTE: expand allowed chars list once we support non-ASCII display names (i18n phase 2)

SAFE_STRING_RE = re.compile(r'[^\w\s\.\-@,]')


def sanitize_string(value: str) -> str:
    """Strip characters that have no place in plain-text fields."""
    if not isinstance(value, str):
        return ''
    return SAFE_STRING_RE.sub('', value).strip()


def validate_pin_format(pin: str) -> bool:
    """Return True if pin is numeric and exactly 8 digits long."""
    if not isinstance(pin, str):
        return False
    return bool(re.fullmatch(r'\d{8}', pin))


def validate_email(email: str) -> bool:
    """Lightweight email sanity check — not a full RFC 5322 parser."""
    if not isinstance(email, str):
        return False
    # TODO: replace with a proper library once we add user registration flow
    pattern = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}$')
    return bool(pattern.match(email))


def validate_firmware_version(ver: str) -> bool:
    """Firmware strings must follow fw-<major>.<minor>.<patch>."""
    return bool(re.fullmatch(r'fw-\d+\.\d+\.\d+', ver or ''))
