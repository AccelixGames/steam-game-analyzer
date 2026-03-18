"""CheapShark API client — game deal/price data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class CheapSharkClient(BaseClient):
    """Fetches game deal ratings and price history from CheapShark."""

    BASE_URL = "https://www.cheapshark.com/api/1.0"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=10.0)

    def search_by_steam_appid(self, appid: int) -> dict | None:
        """Search CheapShark by Steam appid. Returns best deal or None."""
        response = self.get(
            f"{self.BASE_URL}/deals",
            params={"steamAppID": appid, "sortBy": "Rating", "pageSize": 1},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        deals = response.json()
        if not deals:
            return None
        return deals[0]

    def fetch_game_details(self, cheapshark_game_id: str) -> dict | None:
        """Fetch full game details including price history."""
        response = self.get(
            f"{self.BASE_URL}/games",
            params={"id": cheapshark_game_id},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
