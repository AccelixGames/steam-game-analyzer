"""SteamSpy API client."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.models.game import GameSummary

STEAMSPY_BASE = "https://steamspy.com/api.php"


class SteamSpyClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steamspy", default_delay_ms=1000,
            ),
        )

    def fetch_by_tag(self, tag: str, limit: int | None = None, source_prefix: str = "tag") -> list[GameSummary]:
        response = self._client.get(STEAMSPY_BASE, params={"request": "tag", "tag": tag})
        response.raise_for_status()
        return self._parse_game_list(response.json(), f"{source_prefix}:{tag}", limit)

    def fetch_by_genre(self, genre: str, limit: int | None = None) -> list[GameSummary]:
        response = self._client.get(STEAMSPY_BASE, params={"request": "genre", "genre": genre})
        response.raise_for_status()
        return self._parse_game_list(response.json(), f"genre:{genre}", limit)

    def fetch_top100(self, limit: int | None = None) -> list[GameSummary]:
        response = self._client.get(STEAMSPY_BASE, params={"request": "top100in2weeks"})
        response.raise_for_status()
        return self._parse_game_list(response.json(), "top100", limit)

    def fetch_app_details(self, appid: int) -> GameSummary:
        response = self._client.get(STEAMSPY_BASE, params={"request": "appdetails", "appid": str(appid)})
        response.raise_for_status()
        return GameSummary.from_steamspy(response.json())

    def _parse_game_list(self, data: dict, source_tag: str, limit: int | None) -> list[GameSummary]:
        games = [
            GameSummary.from_steamspy(v, source_tag=source_tag)
            for v in data.values()
            if isinstance(v, dict) and "appid" in v
        ]
        games.sort(key=lambda g: g.positive or 0, reverse=True)
        if limit:
            games = games[:limit]
        return games

    def close(self):
        self._client.close()
