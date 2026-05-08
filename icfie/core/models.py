"""Pydantic models for data validation throughout pipeline."""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4, UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict
from .enums import GeoAccuracy, RecordStatus, ExportReadiness


class GeoPoint(BaseModel):
    """Geographic coordinate with validation."""
    model_config = ConfigDict(frozen=True)

    latitude: float = Field(..., ge=8.0, le=37.0, description="India latitude bounds")
    longitude: float = Field(..., ge=68.0, le=97.0, description="India longitude bounds")
    accuracy: GeoAccuracy = GeoAccuracy.UNKNOWN

    @field_validator('latitude')
    @classmethod
    def validate_india_latitude(cls, v: float) -> float:
        if not 8.0 <= v <= 37.0:
            raise ValueError(f"Latitude {v} outside India bounds")
        return round(v, 6)

    @field_validator('longitude')
    @classmethod
    def validate_india_longitude(cls, v: float) -> float:
        if not 68.0 <= v <= 97.0:
            raise ValueError(f"Longitude {v} outside India bounds")
        return round(v, 6)


class EstateDiscovery(BaseModel):
    """Raw discovery record from Phase 1."""
    model_config = ConfigDict(extra="allow")

    source: str
    estate_name_raw: str
    district: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    address_raw: Optional[str] = None
    place_id: Optional[str] = None
    category: Optional[str] = None

    # Internal tracking
    discovery_batch_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class EstateEnrichment(BaseModel):
    """Phase 2-3 enrichment data."""
    model_config = ConfigDict(extra="allow")

    estate_id: UUID = Field(default_factory=uuid4)

    # Phase 2: Text corpus
    website_markdown: Optional[str] = None
    social_bio: Optional[str] = None
    social_captions_sample: Optional[str] = None

    # Phase 3: LLM extraction
    estate_name: Optional[str] = None
    varietals_grown: Optional[List[str]] = None
    processing_methods: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    farm_size_acres: Optional[float] = None
    contact_person: Optional[str] = None
    export_mentions: bool = False
    address_hint: Optional[str] = None
    llm_confidence_score: Optional[float] = None
    llm_confidence_reasoning: Optional[str] = None


class EstateRecord(BaseModel):
    """Complete estate record (Tier 1 + 2 + 3)."""

    # Tier 1: Mandatory Core
    estate_id: str = Field(default_factory=lambda: str(uuid4()))
    estate_name: str = Field(..., min_length=3)
    state: str
    district: str
    latitude: Optional[float] = Field(None, ge=8.0, le=37.0)
    longitude: Optional[float] = Field(None, ge=68.0, le=97.0)
    geo_accuracy: GeoAccuracy = GeoAccuracy.UNKNOWN
    discovery_sources: List[str] = Field(..., min_length=1)
    record_status: RecordStatus = RecordStatus.PENDING_VERIFICATION

    # Tier 2: High-Value Optional
    estate_name_raw: Optional[str] = None
    legal_entity_name: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_contact: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram_handle: Optional[str] = None
    address_raw: Optional[str] = None

    # Tier 3: Full Enrichment
    village_taluka: Optional[str] = None
    varietals_grown: Optional[List[str]] = None
    processing_methods: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    farm_size_acres: Optional[float] = None
    contact_person_name: Optional[str] = None
    export_readiness: ExportReadiness = ExportReadiness.UNKNOWN
    rcmc_verified: bool = False
    apeda_registered: bool = False
    quality_flag: List[str] = Field(default_factory=list)
    bhuvan_verified: Optional[bool] = None
    llm_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    last_enriched_at: datetime = Field(default_factory=datetime.utcnow)

    # Computed
    contactable: bool = False

    @field_validator('estate_name')
    @classmethod
    def validate_name_length(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Estate name must be at least 3 characters")
        return v.strip()

    def model_post_init(self, __context) -> None:
        """Compute contactable flag after initialization."""
        self.contactable = any([
            self.primary_phone,
            self.secondary_contact,
            self.email,
            self.website,
            self.instagram_handle
        ])

    def to_db_dict(self) -> dict:
        """Convert to database-compatible dictionary."""
        data = self.model_dump()
        # Handle enum conversions
        data['geo_accuracy'] = self.geo_accuracy.value
        data['record_status'] = self.record_status.value
        data['export_readiness'] = self.export_readiness.value
        data['discovery_sources'] = list(self.discovery_sources)
        data['quality_flag'] = list(self.quality_flag)
        data['varietals_grown'] = self.varietals_grown
        data['processing_methods'] = self.processing_methods
        data['certifications'] = self.certifications
        return data


class QuarantineRecord(BaseModel):
    """Record that failed validation with reason."""
    model_config = ConfigDict(extra="allow")

    raw_data: dict
    failure_reason: str
    failure_phase: str
    failed_at: datetime = Field(default_factory=datetime.utcnow)
    suggested_action: Optional[str] = None