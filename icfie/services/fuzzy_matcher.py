"""Fuzzy matching utilities."""

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

def is_match(name1: str, name2: str, threshold: int = 85) -> bool:
    if not name1 or not name2:
        return False

    if HAS_RAPIDFUZZ:
        return fuzz.token_set_ratio(name1.lower(), name2.lower()) >= threshold

    return name1.lower() == name2.lower()