"""Phase 2: Deep Web & Social Intelligence."""

import asyncio
import logging
import json
from typing import List, Dict, Any

from ..config.settings import Settings
from ..integrations.apify_client import ApifyClient
from ..integrations.google_client import GoogleClient
from ..core.models import EstateEnrichment

logger = logging.getLogger("icfie.phase2")

class DeepWebEnricher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.apify = ApifyClient(settings.APIFY_API_TOKEN)
        self.google = GoogleClient(settings.GOOGLE_API_KEY)

    async def run(self, raw_seeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Crawl websites and social profiles."""
        logger.info(f"Starting Phase 2 for {len(raw_seeds)} seeds")

        # Extract URLs
        urls = []
        url_to_seed = {}
        for i, seed in enumerate(raw_seeds):
            # Assign temporary ID for tracking
            seed["_temp_id"] = i

            url = seed.get("website")
            if url and url.startswith("http"):
                urls.append(url)
                url_to_seed[url] = i

            # Also check Serper links
            link = seed.get("link")
            if link and link.startswith("http"):
                urls.append(link)
                url_to_seed[link] = i

        # Crawl websites and Facebook
        crawled_data = {}
        fb_data = {}
        if urls:
            crawled_data = await self.apify.crawl_website_text(urls)
            fb_data = await self.apify.run_facebook_enrichment(urls)

        # Fetch Google Place Details
        place_details_cache = {}
        if self.google.is_available:
            place_ids = [s.get("place_id") for s in raw_seeds if s.get("place_id")]
            if place_ids:
                details_tasks = [self.google.get_place_details(pid) for pid in set(place_ids)]
                details_results = await asyncio.gather(*details_tasks, return_exceptions=True)
                for pid, detail in zip(set(place_ids), details_results):
                    if isinstance(detail, dict):
                        place_details_cache[pid] = detail

        # Fetch Google Elevation
        elevation_cache = {}
        if self.google.is_available:
            coords = [(s.get("latitude"), s.get("longitude")) for s in raw_seeds if s.get("latitude") and s.get("longitude")]
            if coords:
                elev_tasks = [self.google.get_elevation(lat, lon) for lat, lon in set(coords)]
                elev_results = await asyncio.gather(*elev_tasks, return_exceptions=True)
                for coord, elev in zip(set(coords), elev_results):
                    if isinstance(elev, (int, float)):
                        elevation_cache[coord] = elev

        # Merge back
        corpus_results = []
        for seed in raw_seeds:
            enrichment = EstateEnrichment()

            # Add Google Places details
            pid = seed.get("place_id")
            if pid and pid in place_details_cache:
                detail = place_details_cache[pid]
                if detail.get("phone"):
                    seed["phone"] = detail.get("phone")
                if detail.get("website"):
                    seed["website"] = detail.get("website")
                if detail.get("reviews_markdown"):
                    enrichment.website_markdown = detail.get("reviews_markdown") + "\n\n---\n\n" + (enrichment.website_markdown or "")

            # Add Elevation
            lat, lon = seed.get("latitude"), seed.get("longitude")
            if lat and lon and (lat, lon) in elevation_cache:
                enrichment.altitude_meters = elevation_cache[(lat, lon)]

            # Carry over ratings
            if seed.get("rating"):
                enrichment.rating = seed.get("rating")
                enrichment.user_ratings_total = seed.get("user_ratings_total")

            # Add website data if crawled
            url = seed.get("website") or seed.get("link")

            markdown_parts = []
            if url and url in crawled_data:
                markdown_parts.append(crawled_data[url])

            # Check Facebook specific data
            if url and url in fb_data:
                markdown_parts.append(fb_data[url])

            if markdown_parts:
                enrichment.website_markdown = "\n\n---\n\n".join(markdown_parts)

            # Instagram extraction (basic, full Apify actor cost too much for free tier)
            ig = seed.get("instagram")
            if ig:
                enrichment.social_bio = await self._basic_social_extract(ig)

            corpus_results.append({
                "seed": seed,
                "enrichment": enrichment.model_dump(mode='json')
            })

        logger.info("Phase 2 complete")
        return corpus_results

    async def _basic_social_extract(self, url: str) -> str:
        """Fallback basic extraction for social pages (often blocked, but worth trying)."""
        try:
            import aiohttp
            from bs4 import BeautifulSoup

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        # Try to find meta description
                        meta = soup.find('meta', property='og:description')
                        if meta:
                            return meta.get('content', '')

                        # Try regular description
                        meta = soup.find('meta', attrs={'name': 'description'})
                        if meta:
                            return meta.get('content', '')
        except Exception:
            pass

        return ""