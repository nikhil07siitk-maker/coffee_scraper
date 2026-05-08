"""Phase 2: Deep Web & Social Intelligence."""

import asyncio
import logging
import json
from typing import List, Dict, Any

from ..config.settings import Settings
from ..integrations.apify_client import ApifyClient
from ..core.models import EstateEnrichment

logger = logging.getLogger("icfie.phase2")

class DeepWebEnricher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.apify = ApifyClient(settings.APIFY_API_TOKEN)

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

        # Crawl websites
        crawled_data = {}
        if urls:
            crawled_data = await self.apify.crawl_website_text(urls)

        # Merge back
        corpus_results = []
        for seed in raw_seeds:
            enrichment = EstateEnrichment()

            # Add website data if crawled
            url = seed.get("website") or seed.get("link")
            if url and url in crawled_data:
                enrichment.website_markdown = crawled_data[url]

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