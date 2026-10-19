import re

from email_validator import EmailNotValidError, validate_email

PHONE_PATTERN = re.compile(r"[0-9]{10}")
MIN_PASSWORD_LENGTH = 8


def is_valid_email(value: str) -> bool:
    """True if the value is a syntactically valid email address."""
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def is_valid_phone(value: str) -> bool:
    """True only for exactly 10 ASCII digits (e.g. 0712345678)."""
    return PHONE_PATTERN.fullmatch(value) is not None


def is_valid_password(value: str) -> bool:
    return len(value) >= MIN_PASSWORD_LENGTH