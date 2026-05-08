"""Enumeration definitions for type safety."""

from enum import Enum


class RecordStatus(str, Enum):
    ACTIVE = "active"
    PENDING_VERIFICATION = "pending_verification"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class GeoAccuracy(str, Enum):
    ROOFTOP = "rooftop"
    APPROXIMATE = "approximate"
    DISTRICT_CENTER = "district_center"
    UNKNOWN = "unknown"


class ExportReadiness(str, Enum):
    VERIFIED_EXPORTER = "verified_exporter"
    MENTIONS_EXPORT = "mentions_export"
    DOMESTIC_ONLY = "domestic_only"
    UNKNOWN = "unknown"


class DiscoverySource(str, Enum):
    GOOGLE_MAPS = "google_maps"
    SERPER = "serper"
    BRAVE = "brave"
    OSM = "osm"
    OVERPASS = "overpass"
    MANUAL = "manual"