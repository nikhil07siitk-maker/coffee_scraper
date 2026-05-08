"""Pydantic settings management with environment variable loading."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    APIFY_API_TOKEN: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None
    BRAVE_API_KEY: Optional[str] = None

    # Local LLM
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: int = 120

    # Paths
    RAW_DATA_PATH: str = "./data/raw"
    PROCESSED_PATH: str = "./data/processed"
    OUTPUT_PATH: str = "./data/output"
    QUARANTINE_PATH: str = "./data/quarantine"

    # Government Data Paths
    CBI_RCMC_PDF_PATH: Optional[str] = None
    APEDA_LIST_PATH: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite:///./data/indian_coffee_intel.db"

    # Pipeline Config
    MAX_MAPS_RESULTS: int = 150
    FUZZY_MATCH_THRESHOLD: int = 88
    GEO_DEDUP_DISTANCE_METERS: float = 75.0
    MAX_CONCURRENT_APIFY_RUNS: int = 2
    MAX_CONCURRENT_OLLAMA: int = 3

    # Rate Limiting
    SERPER_MONTHLY_LIMIT: int = 2500
    BRAVE_MONTHLY_LIMIT: int = 2000
    NOMINATIM_RATE_LIMIT_SECONDS: float = 1.0

    @property
    def raw_path(self) -> Path:
        return Path(self.RAW_DATA_PATH)

    @property
    def processed_path(self) -> Path:
        return Path(self.PROCESSED_PATH)

    @property
    def output_path(self) -> Path:
        return Path(self.OUTPUT_PATH)

    @property
    def quarantine_path(self) -> Path:
        return Path(self.QUARANTINE_PATH)

    def ensure_paths(self) -> None:
        """Create all necessary directories."""
        for path in [self.raw_path, self.processed_path, self.output_path,
                     self.quarantine_path, self.raw_path / "govt"]:
            path.mkdir(parents=True, exist_ok=True)
