"""Google APIs client for Places and Elevation."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp

logger = logging.getLogger("icfie.google")

class GoogleClient:
    """Client for Google Places and Elevation APIs."""

    PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
    ELEVATION_URL = "https://maps.googleapis.com/maps/api/elevation/json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search_places(self, query: str) -> List[Dict[str, Any]]:
        """Search Google Places via Text Search."""
        if not self.is_available:
            logger.warning("Google API Key not set. Skipping Places search.")
            return []

        params = {
            "query": query,
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.PLACES_TEXT_SEARCH_URL, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                        logger.error(f"Google Places Search error: {data.get('status')} - {data.get('error_message', '')}")
                        return []

                    results = []
                    for item in data.get("results", []):
                        location = item.get("geometry", {}).get("location", {})

                        result = {
                            "source": "google_places",
                            "place_id": item.get("place_id"),
                            "estate_name_raw": item.get("name"),
                            "latitude": location.get("lat"),
                            "longitude": location.get("lng"),
                            "address_raw": item.get("formatted_address"),
                            "rating": item.get("rating"),
                            "user_ratings_total": item.get("user_ratings_total"),
                            "geo_accuracy": "rooftop" if location else "unknown"
                        }
                        results.append(result)

                    return results
        except Exception as e:
            logger.error(f"Google Places search failed: {e}")
            return []

    async def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get rich details for a Place ID."""
        if not self.is_available or not place_id:
            return None

        params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,website,reviews",
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.PLACE_DETAILS_URL, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get("status") != "OK":
                        logger.error(f"Google Place Details error: {data.get('status')}")
                        return None

                    result = data.get("result", {})

                    # Format reviews into markdown
                    reviews_markdown = ""
                    reviews = result.get("reviews", [])
                    if reviews:
                        reviews_markdown = "Google Reviews:\n"
                        for r in reviews:
                            reviews_markdown += f"- {r.get('text', '')}\n"

                    return {
                        "phone": result.get("formatted_phone_number"),
                        "website": result.get("website"),
                        "reviews_markdown": reviews_markdown
                    }
        except Exception as e:
            logger.error(f"Google Place Details failed: {e}")
            return None

    async def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """Fetch elevation for given coordinates."""
        if not self.is_available or lat is None or lon is None:
            return None

        params = {
            "locations": f"{lat},{lon}",
            "key": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.ELEVATION_URL, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get("status") == "OK" and data.get("results"):
                        return data["results"][0].get("elevation")

            return None
        except Exception as e:
            logger.error(f"Google Elevation failed: {e}")
            return None