"""OSM Overpass QL builder & executor."""

import asyncio
import json
import logging
from typing import List, Dict, Any, Tuple
import time

import aiohttp

logger = logging.getLogger("icfie.overpass")

class OverpassClient:
    """Overpass API client with rate limiting."""

    BASE_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self):
        self._last_request_time = 0.0
        self._rate_limit = 1.0  # seconds between requests

    async def query_coffee_estates(self, district: str) -> List[Dict[str, Any]]:
        """
        Builds Overpass QL to find ways/nodes with coffee crops or estate names.
        """
        # Ensure rate limit
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            await asyncio.sleep(self._rate_limit - elapsed)

        # Build query
        query = f"""
        [out:json][timeout:60];
        area["name"="{district}"]->.searchArea;
        (
          node["crop"="coffee"](area.searchArea);
          way["crop"="coffee"](area.searchArea);
          node["name"~"Estate|Plantation",i]["landuse"="farmland"](area.searchArea);
          way["name"~"Estate|Plantation",i]["landuse"="farmland"](area.searchArea);
        );
        out center;
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.BASE_URL, data={"data": query}) as response:
                    self._last_request_time = time.time()

                    if response.status == 429:
                        logger.warning("Overpass rate limited, backing off")
                        await asyncio.sleep(10)
                        return []

                    response.raise_for_status()
                    data = await response.json()

                    results = []
                    for element in data.get("elements", []):
                        tags = element.get("tags", {})

                        # Determine coordinates
                        lat = element.get("lat") or element.get("center", {}).get("lat")
                        lon = element.get("lon") or element.get("center", {}).get("lon")

                        if not lat or not lon:
                            continue

                        result = {
                            "source": "osm",
                            "estate_name_raw": tags.get("name", "Unknown Estate"),
                            "district": district,
                            "latitude": lat,
                            "longitude": lon,
                            "address_raw": tags.get("addr:full", ""),
                            "phone": tags.get("phone", tags.get("contact:phone", "")),
                            "website": tags.get("website", tags.get("contact:website", "")),
                            "geo_accuracy": "rooftop" if element.get("type") == "way" else "approximate",
                            "osm_id": element.get("id"),
                            "osm_type": element.get("type")
                        }
                        results.append(result)

                    logger.info(f"Overpass discovery: {len(results)} estates in {district}")
                    return results

        except Exception as e:
            logger.error(f"Overpass query failed: {e}")
            return []