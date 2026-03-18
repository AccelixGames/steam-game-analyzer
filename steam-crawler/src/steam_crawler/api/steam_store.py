"""Steam Store API client for game details (descriptions, images, videos)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter

STORE_BASE = "https://store.steampowered.com/api/appdetails"


@dataclass
class MediaItem:
    media_type: str  # 'screenshot' or 'movie'
    media_id: int
    name: str | None = None
    url_thumbnail: str | None = None
    url_full: str | None = None


@dataclass
class StoreDetails:
    appid: int
    short_description: str | None = None
    detailed_description: str | None = None
    header_image: str | None = None
    website: str | None = None
    media: list[MediaItem] = field(default_factory=list)

    @classmethod
    def from_steam_api(cls, appid: int, data: dict[str, Any]) -> StoreDetails:
        media = []

        for ss in data.get("screenshots", []):
            media.append(MediaItem(
                media_type="screenshot",
                media_id=ss.get("id", 0),
                url_thumbnail=ss.get("path_thumbnail"),
                url_full=ss.get("path_full"),
            ))

        for mv in data.get("movies", []):
            webm = mv.get("webm", {})
            mp4 = mv.get("mp4", {})
            media.append(MediaItem(
                media_type="movie",
                media_id=mv.get("id", 0),
                name=mv.get("name"),
                url_thumbnail=mv.get("thumbnail"),
                url_full=mp4.get("max") or mp4.get("480") or webm.get("max"),
            ))

        return cls(
            appid=appid,
            short_description=data.get("short_description"),
            detailed_description=data.get("detailed_description"),
            header_image=data.get("header_image"),
            website=data.get("website"),
            media=media,
        )


class SteamStoreClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steam_store", default_delay_ms=1500,
            ),
        )

    def fetch_app_details(self, appid: int) -> StoreDetails | None:
        """Fetch store page details for a game. Returns None if not found."""
        response = self._client.get(
            STORE_BASE, params={"appids": str(appid), "cc": "us", "l": "en"}
        )
        response.raise_for_status()
        data = response.json()

        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return None

        return StoreDetails.from_steam_api(appid, app_data["data"])

    def close(self):
        self._client.close()
