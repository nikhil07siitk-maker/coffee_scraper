"""Phase 4: Authority Verification."""

import logging
from typing import List, Dict, Any, Set
from pathlib import Path

from ..config.settings import Settings

logger = logging.getLogger("icfie.phase4")

class AuthorityVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rcmc_set = self._load_cbi_rcmc_names()
        self.apeda_set = self._load_apeda_names()

    def _load_cbi_rcmc_names(self) -> Set[str]:
        """Mock loading for now, would parse PDF/HTML."""
        names = set()
        if self.settings.CBI_RCMC_PDF_PATH:
            path = Path(self.settings.CBI_RCMC_PDF_PATH)
            if path.exists():
                # In full version: use pdfplumber here
                logger.info("RCMC PDF found, skipping parse in MVP")
        return names

    def _load_apeda_names(self) -> Set[str]:
        names = set()
        if self.settings.APEDA_LIST_PATH:
            path = Path(self.settings.APEDA_LIST_PATH)
            if path.exists():
                logger.info("APEDA list found, skipping parse in MVP")
        return names

    def run(self, enriched_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Verify export status and registries."""
        logger.info(f"Starting Phase 4 for {len(enriched_records)} records")

        try:
            from rapidfuzz import fuzz
            has_fuzz = True
        except ImportError:
            has_fuzz = False
            logger.warning("rapidfuzz not installed, using exact matching")

        for record in enriched_records:
            seed = record["seed"]
            enrichment = record["enrichment"]

            # Determine best name to check
            name_to_check = enrichment.get("estate_name") or seed.get("estate_name_raw")
            if not name_to_check:
                continue

            name_to_check = name_to_check.lower()

            # 1. Check RCMC
            rcmc_verified = False
            if has_fuzz and self.rcmc_set:
                for rcmc_name in self.rcmc_set:
                    if fuzz.token_set_ratio(name_to_check, rcmc_name.lower()) >= 85:
                        rcmc_verified = True
                        break
            elif name_to_check in [n.lower() for n in self.rcmc_set]:
                rcmc_verified = True

            enrichment["rcmc_verified"] = rcmc_verified

            # 2. Check APEDA
            apeda_registered = False
            if has_fuzz and self.apeda_set:
                for apeda_name in self.apeda_set:
                    if fuzz.token_set_ratio(name_to_check, apeda_name.lower()) >= 85:
                        apeda_registered = True
                        break
            elif name_to_check in [n.lower() for n in self.apeda_set]:
                apeda_registered = True

            enrichment["apeda_registered"] = apeda_registered

            # 3. Determine Export Readiness
            if rcmc_verified or apeda_registered:
                enrichment["export_readiness"] = "verified_exporter"
            elif enrichment.get("export_mentions"):
                enrichment["export_readiness"] = "mentions_export"
            else:
                enrichment["export_readiness"] = "unknown"

            # Update quality flags
            flags = []
            if rcmc_verified: flags.append("rcmc_holder")
            if apeda_registered: flags.append("apeda_exporter")

            # Add "flavour_of_india" if found via search
            if seed.get("source") == "serper" and "flavour of india" in seed.get("query", "").lower():
                flags.append("flavour_of_india_winner")

            enrichment["quality_flag"] = flags

        logger.info("Phase 4 complete")
        return enriched_records