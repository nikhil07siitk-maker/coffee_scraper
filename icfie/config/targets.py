"""Master list of Indian coffee-growing regions."""

INDIAN_COFFEE_STATES = [
    "Karnataka",
    "Kerala",
    "Tamil Nadu",
    "Andhra Pradesh",
    "Odisha",
    "Assam",      # Northeast
    "Manipur",    # Northeast
    "Meghalaya",  # Northeast
    "Mizoram",    # Northeast
    "Nagaland",   # Northeast
    "Tripura",    # Northeast
    "Arunachal Pradesh",  # Northeast
]

# Major coffee districts by state
COFFEE_DISTRICTS = {
    "Karnataka": [
        "Chikmagalur", "Chikkamagaluru",
        "Kodagu", "Coorg",
        "Hassan",
        "Shimoga", "Shivamogga",
        "Mysore", "Mysuru",
        "Baba Budan Giri"
    ],
    "Kerala": [
        "Wayanad",
        "Idukki",
        "Kozhikode",
        "Malappuram"
    ],
    "Tamil Nadu": [
        "Nilgiris",
        "Coimbatore",
        "Salem",
        "Dindigul",
        "Madurai",
        "Theni"
    ],
    "Andhra Pradesh": [
        "Araku Valley",
        "Visakhapatnam",
        "East Godavari",
        "West Godavari"
    ],
    "Odisha": [
        "Koraput",
        "Rayagada",
        "Kalahandi",
        "Gajapati"
    ],
    "Assam": ["Dima Hasao", "Karbi Anglong"],
    "Manipur": ["Ukhrul", "Tamenglong"],
    "Meghalaya": ["East Garo Hills", "West Khasi Hills"],
    "Nagaland": ["Wokha", "Mon"],
    "Arunachal Pradesh": ["Changlang", "Lohit"],
}

# Normalize district names (handle alternate spellings)
DISTRICT_ALIASES = {
    "chikmagalur": "Chikmagalur",
    "chikkamagaluru": "Chikmagalur",
    "coorg": "Kodagu",
    "mysore": "Mysuru",
    "shimoga": "Shivamogga",
    "nilgiris": "Nilgiris",
}


def normalize_district(district: str) -> str:
    """Normalize district name to standard form."""
    normalized = district.lower().strip()
    return DISTRICT_ALIASES.get(normalized, district.title())


def validate_state_district(state: str, district: str) -> tuple[str, str]:
    """Validate and normalize state/district combination."""
    state_title = state.title()
    district_normalized = normalize_district(district)

    if state_title not in INDIAN_COFFEE_STATES:
        raise ValueError(f"State '{state}' not in recognized coffee-growing states")

    # Allow unknown districts (new discoveries possible)
    known_districts = COFFEE_DISTRICTS.get(state_title, [])
    if district_normalized not in known_districts:
        # Log warning but allow
        pass

    return state_title, district_normalized
