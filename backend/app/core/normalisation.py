"""Contact normalisation utilities for phone numbers (E.164) and email addresses."""

import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email
from phonenumbers import NumberParseException, PhoneNumberFormat

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError

_WHITESPACE_RE = re.compile(r"\s+")


def normalise_email(email: str | None) -> str | None:
    """Validate and normalise an email address to lowercase trimmed canonical form."""
    if email is None:
        return None
    cleaned = email.strip()
    if not cleaned:
        return None
    try:
        info = validate_email(cleaned, check_deliverability=False)
        return info.normalized.lower()
    except EmailNotValidError as exc:
        raise ValidationAppError(
            message=f"Invalid email address: '{email}'.",
            details={"field": "email", "reason": str(exc)},
        ) from exc


def normalise_phone(
    phone: str | None, default_region: str | None = None
) -> str | None:
    """Parse and normalise a phone number into strict E.164 format.

    Supports international inputs (e.g., '+234 803 123 4567', '+44 7700 900123')
    and local numbers parsed against `default_region` (defaults to settings.default_phone_region).
    """
    if phone is None:
        return None
    cleaned = _WHITESPACE_RE.sub("", phone.strip())
    if not cleaned:
        return None

    # Handle leading '00' international dialing prefix -> '+'
    if cleaned.startswith("00") and len(cleaned) > 6:
        cleaned = f"+{cleaned[2:]}"

    region = default_region or get_settings().default_phone_region

    try:
        parsed = phonenumbers.parse(cleaned, None if cleaned.startswith("+") else region)
    except NumberParseException as exc:
        raise ValidationAppError(
            message=f"Invalid phone number: '{phone}'.",
            details={"field": "phone", "reason": str(exc)},
        ) from exc

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(
        parsed
    ):
        raise ValidationAppError(
            message=f"Phone number '{phone}' is not a valid telephone number.",
            details={"field": "phone", "region": region},
        )

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
