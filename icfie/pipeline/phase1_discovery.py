"""Phase 1: Seed generation."""

import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from ..config.settings import Settings
from ..integrations.apify_client import ApifyClient
from ..integrations.serper_client import SerperClient
from ..integrations.brave_client import BraveClient
from ..integrations.overpass_client import OverpassClient

logger = logging.getLogger("icfie.phase1")

class DiscoveryOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.apify = ApifyClient(settings.APIFY_API_TOKEN)
        self.serper = SerperClient(settings.SERPER_API_KEY, settings.SERPER_MONTHLY_LIMIT)
        self.brave = BraveClient(settings.BRAVE_API_KEY, settings.BRAVE_MONTHLY_LIMIT)
        self.overpass = OverpassClient()

    async def run(self, district: str, state: str) -> List[Dict[str, Any]]:
        logger.info(f"Starting Phase 1 Discovery for {district}, {state}")

        # Parallel execution of discovery sources
        tasks = [
            self._run_maps(district, state),
            self._run_search(district, state),
            self._run_osm(district),
            self._run_indiamart(district, state),
            self._run_justdial(district, state)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_seeds = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Discovery task {i} failed: {res}")
            elif isinstance(res, list):
                all_seeds.extend(res)

        # Deduplicate raw seeds simply to reduce Phase 2 load
        # Phase 5 will do rigorous deduplication
        unique_seeds = self._basic_dedup(all_seeds)

        # Save raw output
        self._save_raw_output(unique_seeds, district)

        logger.info(f"Phase 1 complete. Found {len(unique_seeds)} unique seeds.")
        return unique_seeds

    async def _run_maps(self, district: str, state: str) -> List[Dict]:
        return await self.apify.run_google_maps_discovery(
            district, state, max_results=self.settings.MAX_MAPS_RESULTS
        )

    async def _run_search(self, district: str, state: str) -> List[Dict]:
        # Try Serper first
        if self.serper.is_available:
            return await self.serper.search_estate_mentions(district, state)

        # Fallback to Brave
        if self.brave.is_available:
            logger.info("Using Brave search as fallback")
            return await self.brave.search_estate_mentions(district, state)

        return []

    async def _run_osm(self, district: str) -> List[Dict]:
        return await self.overpass.query_coffee_estates(district)

    async def _run_indiamart(self, district: str, state: str) -> List[Dict]:
        return await self.apify.run_indiamart_discovery(district, state)

    async def _run_justdial(self, district: str, state: str) -> List[Dict]:
        return await self.apify.run_justdial_discovery(district, state)

    def _basic_dedup(self, seeds: List[Dict]) -> List[Dict]:
        """Simple deduplication to prevent crawling the same site multiple times."""
        seen_names = set()
        seen_urls = set()
        unique = []

        for seed in seeds:
            name = seed.get("estate_name_raw", "").lower().strip()
            url = seed.get("website", "")

            # Skip empty names
            if not name:
                continue

            # Check URL first (strongest indicator)
            if url and url in seen_urls:
                continue

            # Check name if no URL or URL not seen
            if name in seen_names:
                continue

            seen_names.add(name)
            if url:
                seen_urls.add(url)

            unique.append(seed)

        return unique

    def _save_raw_output(self, seeds: List[Dict], district: str) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"phase1_{district.lower()}_{timestamp}.jsonl"
        filepath = self.settings.raw_path / filename

        with open(filepath, "w") as f:
            for seed in seeds:
                f.write(json.dumps(seed) + "\n")