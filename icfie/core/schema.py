"""Field constants and validators for pipeline consistency."""

import re
from typing import Pattern, Optional

# Field name constants
TIER1_FIELDS = [
    'estate_id', 'estate_name', 'state', 'district',
    'latitude', 'longitude', 'geo_accuracy',
    'discovery_sources', 'record_status'
]

TIER2_FIELDS = [
    'estate_name_raw', 'legal_entity_name',
    'primary_phone', 'secondary_contact', 'email',
    'website', 'instagram_handle', 'address_raw'
]

TIER3_FIELDS = [
    'village_taluka', 'varietals_grown', 'processing_methods',
    'certifications', 'farm_size_acres', 'contact_person_name',
    'export_readiness', 'rcmc_verified', 'apeda_registered',
    'quality_flag', 'bhuvan_verified', 'llm_confidence_score',
    'last_enriched_at'
]

ALL_FIELDS = TIER1_FIELDS + TIER2_FIELDS + TIER3_FIELDS

# Validation patterns
INDIAN_PHONE_PATTERN: Pattern = re.compile(
    r'^(?:\+91[\-\s]?)?[0]?(91)?[789]\d{9}$'
)

EMAIL_PATTERN: Pattern = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

INSTAGRAM_PATTERN: Pattern = re.compile(
    r'(?:@|instagram\.com/)([a-zA-Z0-9_.]{1,30})'
)

URL_PATTERN: Pattern = re.compile(
    r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
)

# Coffee-specific constants
KNOWN_VARIETALS = [
    "S795", "CxR", "Raro", "Chandragiri", "Kent",
    "Selection 9", "Selection 10", "Selection 11",
    "Arabica", "Robusta", "Liberica", "Excelsa",
    "Catimor", "Caturra", "Bourbon", "Typica"
]

KNOWN_PROCESSING = [
    "Washed", "Wet Processed", "Fully Washed",
    "Natural", "Dry Processed", "Sun Dried",
    "Honey", "Pulped Natural", "Semi Washed",
    "Monsooned", "Anaerobic", "Carbonic Maceration"
]

KNOWN_CERTIFICATIONS = [
    "Organic", "USDA Organic", "Jaivik Bharat",
    "Rainforest Alliance", "UTZ", "Fairtrade",
    "Fair Trade", "Shade Grown", "Bird Friendly",
    "Demeter", "BioDynamic"
]


def validate_phone(phone: str) -> Optional[str]:
    """Normalize and validate Indian phone number."""
    if not phone:
        return None

    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)

    # Handle various formats
    if len(digits) == 10 and digits[0] in '789':
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith('91') and digits[2] in '789':
        return f"+{digits}"
    elif len(digits) == 11 and digits.startswith('0') and digits[1] in '789':
        return f"+91{digits[1:]}"

    return None  # Invalid format


def mask_phone_for_logs(phone: str) -> str:
    """Mask middle digits of phone for logging."""
    if not phone or len(phone) < 10:
        return "***"
    return f"{phone[:4]}****{phone[-4:]}"


def validate_email(email: str) -> Optional[str]:
    """Validate email format."""
    if not email:
        return None
    if EMAIL_PATTERN.match(email.strip()):
        return email.strip().lower()
    return None