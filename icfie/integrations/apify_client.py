"""Apify actor runner with rate limiting and resilience."""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import time

from apify_client import ApifyClient as OfficialApifyClient
from apify_client._errors import ApifyApiError

logger = logging.getLogger("icfie.apify")

class ApifyClient:
    """Managed Apify client with circuit breaker and rate limiting."""

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.client = OfficialApifyClient(token) if token else None
        self._failure_count = 0
        self._circuit_open = False
        self._last_failure_time: Optional[float] = None
        self._active_runs = 0
        self._max_concurrent = 2
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._run_lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        """Check if client is usable (circuit closed and token present)."""
        if not self.token or not self.client:
            return False
        if self._circuit_open:
            # Try half-open after 5 minutes
            if self._last_failure_time and (time.time() - self._last_failure_time) > 300:
                self._circuit_open = False
                self._failure_count = 0
                logger.info("Circuit breaker half-open, attempting retry")
                return True
            return False
        return True

    def _record_failure(self) -> None:
        """Record integration failure for circuit breaker."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= 3:
            self._circuit_open = True
            logger.critical("Circuit breaker OPEN for Apify - skipping for remainder")

    def _record_success(self) -> None:
        """Reset failure count on success."""
        self._failure_count = 0

    async def run_google_maps_discovery(
        self,
        district: str,
        state: str,
        search_terms: List[str] = None,
        max_results: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Trigger Google Maps scraper for coffee estate discovery.

        Uses compass/google-maps-scraper actor with free-tier constraints.
        """
        if not self.token:
            logger.warning("Apify API token not set, skipping Google Maps discovery")
            return []

        if not self.is_available:
            logger.warning("Apify circuit breaker open, skipping Google Maps discovery")
            return []

        search_terms = search_terms or ["coffee estate", "coffee plantation", "coffee works"]
        all_results = []

        async with self._semaphore:
            for term in search_terms:
                try:
                    results = await self._run_single_maps_search(
                        district, state, term, max_results // len(search_terms)
                    )
                    all_results.extend(results)

                    # Rate limit between searches
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Maps search failed for '{term}': {e}")
                    self._record_failure()

        self._record_success()
        logger.info(f"Google Maps discovery complete: {len(all_results)} raw places")
        return all_results

    async def _run_single_maps_search(
        self,
        district: str,
        state: str,
        search_term: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Execute single Google Maps actor run."""

        search_query = f"{search_term} {district} {state} India"

        run_input = {
            "searchStringsArray": [search_query],
            "locationQuery": f"{district}, {state}, India",
            "maxCrawledPlaces": max_results,
            "includeWebResults": False,
            "language": "en",
            "countryCode": "in",
            "maxImages": 0,  # Save credits
            "scrapeContacts": False,  # Save credits
            "scrapeReviews": False,  # Save credits
        }

        try:
            # Start actor run - fallback to other popular Google Maps scrapers
            # if compass is not available.
            # Using standard apify generic scraper or others like gaspardm/google-maps-scraper
            actor_id = "drobnikj/crawler-google-places"

            # Use sync client in thread pool for async compatibility
            loop = asyncio.get_event_loop()
            try:
                run = await loop.run_in_executor(
                    None,
                    lambda: self.client.actor(actor_id).call(run_input=run_input)
                )
            except ApifyApiError as e:
                # Fallback to another popular actor if first one fails
                logger.warning(f"Actor {actor_id} failed, trying fallback: {e}")
                actor_id = "gaspardm/google-maps-scraper"
                run = await loop.run_in_executor(
                    None,
                    lambda: self.client.actor(actor_id).call(run_input=run_input)
                )

            if not run or not run.get("id"):
                raise ApifyApiError("Failed to start actor run", 500)

            # Wait for completion with timeout
            run_id = run["id"]
            logger.info(f"Started actor run {run_id} for '{search_term}'")

            # Poll for results (free tier may queue)
            max_wait = 600  # 10 minutes
            waited = 0
            while waited < max_wait:
                await asyncio.sleep(5)
                waited += 5

                run_info = await loop.run_in_executor(
                    None,
                    lambda: self.client.run(run_id).get()
                )

                status = run_info.get("status")
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    raise ApifyApiError(f"Run {run_id} {status}", 500)

            # Fetch results from dataset
            dataset_id = run_info.get("defaultDatasetId")
            if not dataset_id:
                return []

            items = []
            offset = 0
            limit = 100

            while True:
                page = await loop.run_in_executor(
                    None,
                    lambda: self.client.dataset(dataset_id).list_items(
                        offset=offset,
                        limit=limit
                    )
                )

                page_items = page.get("items", [])
                if not page_items:
                    break

                items.extend(page_items)
                offset += len(page_items)

                if len(page_items) < limit:
                    break

            # Transform to standard format
            results = []
            for item in items:
                result = {
                    "source": "google_maps",
                    "estate_name_raw": item.get("title", ""),
                    "district": district,
                    "state": state,
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "phone": item.get("phone"),
                    "website": item.get("website"),
                    "instagram": self._extract_instagram(item),
                    "address_raw": item.get("address", item.get("street", "")),
                    "place_id": item.get("placeId"),
                    "category": item.get("categoryName", ""),
                    "geo_accuracy": "approximate" if item.get("location") else "unknown"
                }
                results.append(result)

            return results

        except ApifyApiError as e:
            logger.error(f"Apify API error: {e}")
            self._record_failure()
            raise
        except Exception as e:
            logger.error(f"Unexpected error in maps search: {e}")
            self._record_failure()
            raise

    def _extract_instagram(self, item: Dict) -> Optional[str]:
        """Extract Instagram handle from various possible fields."""
        # Check direct fields
        for field in ["instagram", "instagramHandle", "instagramUrl"]:
            val = item.get(field)
            if val:
                return val

        # Check website for instagram link
        website = item.get("website", "")
        if "instagram.com" in website:
            return website

        # Check description/social media
        desc = item.get("description", "")
        if "@" in desc:
            import re
            match = re.search(r'@([a-zA-Z0-9_.]{1,30})', desc)
            if match:
                return f"https://instagram.com/{match.group(1)}"

        return None

    async def crawl_website_text(
        self,
        urls: List[str],
        max_pages: int = 10,
        max_depth: int = 2
    ) -> Dict[str, str]:
        """
        Crawl estate websites and extract markdown text.

        Uses apify/website-content-crawler actor.
        """
        if not self.is_available or not urls:
            return {}

        # Filter valid URLs
        valid_urls = [u for u in urls if u and u.startswith('http')]
        if not valid_urls:
            return {}

        results = {}

        # Batch URLs to manage costs
        batch_size = 5
        for i in range(0, len(valid_urls), batch_size):
            batch = valid_urls[i:i + batch_size]

            async with self._semaphore:
                try:
                    batch_results = await self._crawl_url_batch(batch, max_pages, max_depth)
                    results.update(batch_results)
                    self._record_success()
                except Exception as e:
                    logger.error(f"Batch crawl failed: {e}")
                    self._record_failure()

                await asyncio.sleep(3)  # Rate limit

        return results

    async def _crawl_url_batch(
        self,
        urls: List[str],
        max_pages: int,
        max_depth: int
    ) -> Dict[str, str]:
        """Crawl a batch of URLs."""

        start_urls = [{"url": u} for u in urls]

        run_input = {
            "startUrls": start_urls,
            "maxCrawlDepth": max_depth,
            "maxPagesPerCrawl": max_pages,
            "outputFormats": ["markdown"],
            "removeElementsCssSelector": "nav, footer, .advertisement, .cookie-banner, #cookie-banner, .newsletter-signup",
            "maxCrawlPages": max_pages * len(urls),
            "waitForSelectorTimeout": 5000,
        }

        try:
            loop = asyncio.get_event_loop()

            actor_id = "apify/website-content-crawler"
            run = await loop.run_in_executor(
                None,
                lambda: self.client.actor(actor_id).call(run_input=run_input)
            )

            if not run or not run.get("id"):
                return {u: "" for u in urls}

            # Wait with shorter timeout for website crawler
            run_id = run["id"]
            max_wait = 300  # 5 minutes
            waited = 0

            while waited < max_wait:
                await asyncio.sleep(3)
                waited += 3

                run_info = await loop.run_in_executor(
                    None,
                    lambda: self.client.run(run_id).get()
                )

                status = run_info.get("status")
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    logger.warning(f"Website crawl {run_id} {status}")
                    return {u: "" for u in urls}

            # Fetch results
            dataset_id = run_info.get("defaultDatasetId")
            if not dataset_id:
                return {u: "" for u in urls}

            # Get all items
            items = []
            offset = 0
            while True:
                page = await loop.run_in_executor(
                    None,
                    lambda: self.client.dataset(dataset_id).list_items(
                        offset=offset, limit=100
                    )
                )
                page_items = page.get("items", [])
                if not page_items:
                    break
                items.extend(page_items)
                offset += len(page_items)

            # Group by domain
            from urllib.parse import urlparse
            domain_texts: Dict[str, List[str]] = {}

            for item in items:
                url = item.get("url", "")
                markdown = item.get("markdown", item.get("text", ""))

                if not markdown:
                    continue

                domain = urlparse(url).netloc
                if domain not in domain_texts:
                    domain_texts[domain] = []
                domain_texts[domain].append(markdown)

            # Concatenate per domain
            result = {}
            for url in urls:
                domain = urlparse(url).netloc
                texts = domain_texts.get(domain, [])
                result[url] = "\n\n---\n\n".join(texts) if texts else ""

            return result

        except Exception as e:
            logger.error(f"Website crawl error: {e}")
            raise