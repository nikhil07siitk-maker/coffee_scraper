"""Serper.dev Google Search API client with quota management."""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

import aiohttp

logger = logging.getLogger("icfie.serper")

class SerperClient:
    """Serper.dev client with monthly quota tracking."""

    BASE_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None, monthly_limit: int = 2500):
        self.api_key = api_key
        self.monthly_limit = monthly_limit
        self._quota_file = Path("./data/.serper_quota.json")
        self._request_count = self._load_quota()
        self._last_reset = self._load_reset_date()
        self._failure_count = 0
        self._circuit_open = False
        self._session: Optional[aiohttp.ClientSession] = None

    def _load_quota(self) -> int:
        """Load current month's request count."""
        if self._quota_file.exists():
            try:
                data = json.loads(self._quota_file.read_text())
                saved_month = data.get("month", "")
                current_month = datetime.now().strftime("%Y-%m")
                if saved_month == current_month:
                    return data.get("count", 0)
            except Exception:
                pass
        return 0

    def _load_reset_date(self) -> datetime:
        """Load or initialize quota reset date."""
        if self._quota_file.exists():
            try:
                data = json.loads(self._quota_file.read_text())
                return datetime.fromisoformat(data.get("reset_date", datetime.now().isoformat()))
            except Exception:
                pass
        return datetime.now()

    def _save_quota(self) -> None:
        """Persist quota to disk."""
        self._quota_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "month": datetime.now().strftime("%Y-%m"),
            "count": self._request_count,
            "reset_date": self._last_reset.isoformat()
        }
        self._quota_file.write_text(json.dumps(data))

    @property
    def remaining_quota(self) -> int:
        """Calculate remaining quota for this month."""
        # Check if we need to reset
        now = datetime.now()
        if now.month != self._last_reset.month or now.year != self._last_reset.year:
            self._request_count = 0
            self._last_reset = now
            self._save_quota()

        return max(0, self.monthly_limit - self._request_count)

    @property
    def is_available(self) -> bool:
        """Check if client has quota and circuit is closed."""
        if not self.api_key:
            return False
        if self._circuit_open:
            return False
        if self.remaining_quota <= 0:
            logger.warning("Serper quota exhausted for this month")
            return False
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    'X-API-KEY': self.api_key,
                    'Content-Type': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def search_estate_mentions(
        self,
        district: str,
        state: str,
        queries: Optional[List[str]] = None,
        pages: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Search for coffee estate mentions in district.

        Default queries target estate discovery, contact info, and awards.
        """
        if not self.api_key:
            logger.warning("Serper API key not set, skipping search")
            return []

        if not self.is_available:
            logger.warning("Serper unavailable (circuit breaker or quota), skipping search")
            return []

        if queries is None:
            queries = [
                f'"coffee estate" "{district}" site:.in',
                f'"coffee plantation" "{district}" contact phone',
                f'"flavour of india" "{district}" coffee',
                f'"coffee works" "{district}" "{state}"',
                f'arabica robusta "{district}" estate plantation',
            ]

        all_results = []

        for query in queries:
            # Check quota before each query
            if self.remaining_quota <= 0:
                logger.warning("Serper quota exhausted mid-run")
                break

            try:
                for page in range(pages):
                    results = await self._execute_search(query, page)
                    all_results.extend(results)

                    # Rate limit between pages
                    await asyncio.sleep(1)

                self._failure_count = 0  # Reset on success

            except Exception as e:
                logger.error(f"Search failed for '{query}': {e}")
                self._failure_count += 1
                if self._failure_count >= 3:
                    self._circuit_open = True
                    logger.critical("Serper circuit breaker OPEN")
                    break

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            url = r.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        logger.info(f"Serper discovery: {len(unique_results)} unique results")
        return unique_results

    async def _execute_search(self, query: str, page: int = 0) -> List[Dict]:
        """Execute single search query."""

        payload = {
            "q": query,
            "gl": "in",  # Country: India
            "hl": "en",  # Language: English
            "num": 10,   # Results per page
            "page": page + 1,
        }

        # Add search type for better results
        if "flavour of india" in query.lower():
            payload["type"] = "search"

        session = await self._get_session()

        async with session.post(self.BASE_URL, json=payload) as response:
            if response.status == 403:
                logger.error("Serper API returned 403 Forbidden. Check your API key or quota.")
                self._circuit_open = True
                raise Exception("Forbidden")

            if response.status == 429:
                logger.warning("Serper rate limited, backing off")
                await asyncio.sleep(10)
                raise Exception("Rate limited")

            response.raise_for_status()
            data = await response.json()

            # Track quota
            self._request_count += 1
            self._save_quota()

            # Extract organic results
            organic = data.get("organic", [])
            results = []

            for item in organic:
                result = {
                    "source": "serper",
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position"),
                    "query": query,
                    "page": page,
                }
                results.append(result)

            return results