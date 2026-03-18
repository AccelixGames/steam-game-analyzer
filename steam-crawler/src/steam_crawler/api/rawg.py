"""RAWG Video Games Database API client."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class RAWGClient(BaseClient):
    """RAWG API client. Inherits BaseClient (GET-based API)."""

    BASE_URL = "https://api.rawg.io/api"

    def __init__(
        self,
        api_key: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
    ):
        super().__init__(rate_limiter=rate_limiter)
        self._api_key = api_key

    def _params(self, extra: dict | None = None) -> dict:
        """Build query params with API key included."""
        params = {"key": self._api_key}
        if extra:
            params.update(extra)
        return params

    def search_by_name(self, name: str) -> list[dict]:
        """Search RAWG for games by name. Returns list of result dicts."""
        response = self.get(
            f"{self.BASE_URL}/games",
            params=self._params({"search": name, "page_size": 10}),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def search_by_steam_id(self, appid: int) -> list[dict]:
        """Search RAWG for games available on Steam (store=1).
        Caller checks results for AppID match."""
        response = self.get(
            f"{self.BASE_URL}/games",
            params=self._params({"stores": "1", "page_size": 5}),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def fetch_game_details(self, rawg_id: int) -> dict | None:
        """Fetch full details for a specific RAWG game ID."""
        response = self.get(
            f"{self.BASE_URL}/games/{rawg_id}",
            params=self._params(),
        )
        response.raise_for_status()
        return response.json()
