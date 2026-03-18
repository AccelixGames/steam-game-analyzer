"""OpenCritic API client via RapidAPI — critic review aggregation."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.matching import GameMatcher


class OpenCriticClient(BaseClient):
    """Fetches critic scores and reviews from OpenCritic via RapidAPI."""

    BASE_URL = "https://opencritic-api.p.rapidapi.com"

    def __init__(
        self,
        rapidapi_key: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
    ):
        super().__init__(rate_limiter=rate_limiter, timeout=15.0)
        self._headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "opencritic-api.p.rapidapi.com",
        }

    def search(self, game_name: str) -> dict | None:
        """Search OpenCritic for a game. Returns best match or None."""
        response = self.get(
            f"{self.BASE_URL}/game/search",
            params={"criteria": game_name},
            headers=self._headers,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        matcher = GameMatcher()
        return matcher.best_match(game_name, results, name_key="name")

    def fetch_game(self, opencritic_id: int) -> dict | None:
        """Fetch full game details from OpenCritic."""
        response = self.get(
            f"{self.BASE_URL}/game/{opencritic_id}",
            headers=self._headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def fetch_reviews(self, opencritic_id: int, sort: str = "score") -> list[dict]:
        """Fetch individual critic reviews for a game."""
        response = self.get(
            f"{self.BASE_URL}/game/{opencritic_id}/reviews",
            params={"sort": sort},
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()
