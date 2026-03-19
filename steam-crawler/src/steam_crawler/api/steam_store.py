"""Steam Store API client for game details (descriptions, images, videos)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter

STORE_BASE = "https://store.steampowered.com/api/appdetails"
STORE_PAGE = "https://store.steampowered.com/app"


@dataclass
class MediaItem:
    media_type: str  # 'screenshot' or 'movie'
    media_id: int
    name: str | None = None
    url_thumbnail: str | None = None
    url_full: str | None = None


def _strip_html(html: str | None) -> str | None:
    """Remove HTML tags and decode entities, returning plain text."""
    if not html:
        return None
    # Insert newlines for block-level elements and <br>
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</(p|h[1-6]|li|div|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class StoreDetails:
    appid: int
    name_ko: str | None = None
    short_description_en: str | None = None
    short_description_ko: str | None = None
    detailed_description_en: str | None = None
    detailed_description_ko: str | None = None
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

        # Extract Korean name only if it differs from English
        name_en = data_en.get("name")
        name_ko_raw = data_ko.get("name") if data_ko else None
        name_ko = name_ko_raw if (name_ko_raw and name_ko_raw != name_en) else None

        return cls(
            appid=appid,
            name_ko=name_ko,
            short_description_en=data_en.get("short_description"),
            short_description_ko=data_ko.get("short_description") if data_ko else None,
            detailed_description_en=_strip_html(data_en.get("detailed_description")),
            detailed_description_ko=_strip_html(data_ko.get("detailed_description")) if data_ko else None,
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

    def fetch_similar_appids(self, appid: int) -> list[int]:
        """Fetch 'More Like This' appids from the Steam Store page.

        Parses the embedded JSON config in the store page HTML that contains
        the recommendation carousel's appID list.
        """
        response = self._client.get(f"{STORE_PAGE}/{appid}")
        response.raise_for_status()
        html = response.text

        # The store page embeds similar appIDs as HTML-entity-encoded JSON:
        # &quot;appIDs&quot;:[2670630,1442430,...],...&quot;more_like_this_carousel&quot;
        match = re.search(
            r'&quot;appIDs&quot;:\[([0-9,]+)\].*?more_like_this_carousel',
            html,
        )
        if not match:
            return []

        try:
            raw_ids = json.loads(f"[{match.group(1)}]")
            return [int(aid) for aid in raw_ids if int(aid) != appid]
        except (json.JSONDecodeError, ValueError):
            return []

    def close(self):
        self._client.close()
