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
    short_description_en: str | None = None
    short_description_ko: str | None = None
    header_image: str | None = None
    website: str | None = None
    media: list[MediaItem] = field(default_factory=list)

    @classmethod
    def from_steam_api(cls, appid: int, data_en: dict[str, Any],
                       data_ko: dict[str, Any] | None = None) -> StoreDetails:
        media = []

        for ss in data_en.get("screenshots", []):
            media.append(MediaItem(
                media_type="screenshot",
                media_id=ss.get("id", 0),
                url_thumbnail=ss.get("path_thumbnail"),
                url_full=ss.get("path_full"),
            ))

        for mv in data_en.get("movies", []):
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
            short_description_en=data_en.get("short_description"),
            short_description_ko=data_ko.get("short_description") if data_ko else None,
            header_image=data_en.get("header_image"),
            website=data_en.get("website"),
            media=media,
        )


class SteamStoreClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steam_store", default_delay_ms=1500,
            ),
        )

    def _fetch_raw(self, appid: int, lang: str = "en") -> dict | None:
        """Fetch raw app data for a language. Returns None if not found."""
        response = self._client.get(
            STORE_BASE, params={"appids": str(appid), "cc": "us", "l": lang}
        )
        response.raise_for_status()
        data = response.json()
        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return None
        return app_data["data"]

    def fetch_app_details(self, appid: int) -> StoreDetails | None:
        """Fetch store page details in English + Korean."""
        data_en = self._fetch_raw(appid, lang="english")
        if data_en is None:
            return None

        data_ko = self._fetch_raw(appid, lang="koreana")

        return StoreDetails.from_steam_api(appid, data_en, data_ko)

    def close(self):
        self._client.close()
