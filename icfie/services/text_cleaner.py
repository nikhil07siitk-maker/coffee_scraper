"""Text cleaning and normalization utilities."""

import re

def clean_estate_name(name: str) -> str:
    if not name:
        return ""
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def normalize_phone(phone: str) -> str:
    """Normalize Indian phone numbers."""
    if not phone:
        return ""
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)

    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    elif len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"

    return phone # return as is if unknown format