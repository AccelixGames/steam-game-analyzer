"""ProtonDB API client — Linux/Steam Deck compatibility data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class ProtonDBClient(BaseClient):
    """Fetches ProtonDB compatibility summaries by Steam appid."""

    BASE_URL = "https://www.protondb.com/api/v1/reports/summaries"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=10.0)

    def fetch_summary(self, appid: int) -> dict | None:
        """Fetch ProtonDB summary for a Steam appid.
        Returns None if game not found (404).
        """
        url = f"{self.BASE_URL}/{appid}.json"
        response = self.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
