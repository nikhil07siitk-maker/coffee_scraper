"""Geocoding & reverse geocoding using Nominatim."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
import time

import aiohttp

logger = logging.getLogger("icfie.nominatim")

class NominatimClient:
    """Nominatim client with strict 1 req/sec rate limit."""

    BASE_URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self):
        self._last_request_time = 0.0
        self._rate_limit = 1.0  # seconds between requests (strict OSM policy)
        self._user_agent = "ICFIE_Agent/2.0 (contact: agent@example.com)"

    async def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates to structured address.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit:
            await asyncio.sleep(self._rate_limit - elapsed)

        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "zoom": 14  # Village/suburb level
        }

        headers = {
            "User-Agent": self._user_agent
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    self._last_request_time = time.time()

                    if response.status == 429:
                        logger.warning("Nominatim rate limited, backing off")
                        await asyncio.sleep(5)
                        return None

                    response.raise_for_status()
                    data = await response.json()

                    address = data.get("address", {})

                    # Extract best locality identifier
                    village = address.get("village",
                                address.get("town",
                                address.get("suburb",
                                address.get("hamlet"))))

                    taluka = address.get("county", address.get("municipality"))

                    return {
                        "village_taluka": f"{village}, {taluka}" if village and taluka else village or taluka,
                        "district": address.get("state_district"),
                        "state": address.get("state"),
                        "pincode": address.get("postcode"),
                        "raw_address": data.get("display_name")
                    }

        except Exception as e:
            logger.error(f"Reverse geocoding failed for {lat},{lon}: {e}")
            return None