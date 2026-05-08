"""Brave Search API client (fallback for Serper)."""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

import aiohttp

logger = logging.getLogger("icfie.brave")

class BraveClient:
    """Brave Search client with monthly quota tracking."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: Optional[str] = None, monthly_limit: int = 2000):
        self.api_key = api_key
        self.monthly_limit = monthly_limit
        self._quota_file = Path("./data/.brave_quota.json")
        self._request_count = self._load_quota()
        self._last_reset = self._load_reset_date()
        self._failure_count = 0
        self._circuit_open = False
        self._session: Optional[aiohttp.ClientSession] = None

    def _load_quota(self) -> int:
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
        if self._quota_file.exists():
            try:
                data = json.loads(self._quota_file.read_text())
                return datetime.fromisoformat(data.get("reset_date", datetime.now().isoformat()))
            except Exception:
                pass
        return datetime.now()

    def _save_quota(self) -> None:
        self._quota_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "month": datetime.now().strftime("%Y-%m"),
            "count": self._request_count,
            "reset_date": self._last_reset.isoformat()
        }
        self._quota_file.write_text(json.dumps(data))

    @property
    def remaining_quota(self) -> int:
        now = datetime.now()
        if now.month != self._last_reset.month or now.year != self._last_reset.year:
            self._request_count = 0
            self._last_reset = now
            self._save_quota()

        return max(0, self.monthly_limit - self._request_count)

    @property
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        if self._circuit_open:
            return False
        if self.remaining_quota <= 0:
            logger.warning("Brave quota exhausted for this month")
            return False
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip',
                    'X-Subscription-Token': self.api_key
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
        """Fallback search logic."""
        if not self.is_available:
            return []

        if queries is None:
            queries = [
                f'"coffee estate" "{district}" site:.in',
                f'"coffee plantation" "{district}" contact phone',
            ]

        all_results = []
        for query in queries:
            if self.remaining_quota <= 0:
                break

            try:
                for page in range(pages):
                    results = await self._execute_search(query, page)
                    all_results.extend(results)
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Brave search failed: {e}")

        return all_results

    async def _execute_search(self, query: str, page: int = 0) -> List[Dict]:
        session = await self._get_session()
        params = {
            "q": query,
            "country": "in",
            "search_lang": "en",
            "count": 10,
            "offset": page * 10
        }

        async with session.get(self.BASE_URL, params=params) as response:
            response.raise_for_status()
            data = await response.json()

            self._request_count += 1
            self._save_quota()

            results = []
            web_results = data.get("web", {}).get("results", [])

            for item in web_results:
                results.append({
                    "source": "brave",
                    "title": item.get("title", ""),
                    "link": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "query": query,
                })

            return results