"""PCGamingWiki Cargo API client — technical game data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class PCGamingWikiClient(BaseClient):
    """Fetches technical game info from PCGamingWiki via MediaWiki Cargo API."""

    BASE_URL = "https://www.pcgamingwiki.com/w/api.php"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=15.0)

    def fetch_by_appid(self, appid: int) -> dict | None:
        """Fetch technical data for a Steam game by appid.
        Returns dict with: engine, has_ultrawide, has_hdr, has_controller, graphics_api
        """
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Infobox_game",
            "fields": "Infobox_game._pageName=page,Infobox_game.Engines=engines,"
                      "Infobox_game.Steam_AppID=steam_appid",
            "where": f'Infobox_game.Steam_AppID HOLDS "{appid}"',
            "format": "json",
            "limit": "1",
        })
        response.raise_for_status()
        data = response.json()
        results = data.get("cargoquery", [])
        if not results:
            return None

        row = results[0].get("title", {})
        page_name = row.get("page", "")
        engine = row.get("engines", "")

        video_data = self._fetch_video_settings(page_name)
        input_data = self._fetch_input_settings(page_name)

        return {
            "engine": engine if engine else None,
            "has_ultrawide": video_data.get("has_ultrawide"),
            "has_hdr": video_data.get("has_hdr"),
            "graphics_api": video_data.get("graphics_api"),
            "has_controller": input_data.get("has_controller"),
        }

    def _fetch_video_settings(self, page_name: str) -> dict:
        """Fetch video settings (ultrawide, HDR, graphics API) for a page."""
        result = {"has_ultrawide": None, "has_hdr": None, "graphics_api": None}
        if not page_name:
            return result

        safe_name = page_name.replace('"', '\\"')
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Video",
            "fields": "Video.Ultra_widescreen=ultrawide,"
                      "Video.HDR=hdr,"
                      "Video.API=api",
            "where": f'Video._pageName="{safe_name}"',
            "format": "json",
            "limit": "1",
        })
        if response.status_code != 200:
            return result

        data = response.json()
        rows = data.get("cargoquery", [])
        if not rows:
            return result

        row = rows[0].get("title", {})
        uw = row.get("ultrawide", "")
        result["has_ultrawide"] = uw.lower() == "true" if uw else None
        hdr_val = row.get("hdr", "")
        result["has_hdr"] = hdr_val.lower() == "true" if hdr_val else None
        result["graphics_api"] = row.get("api") or None
        return result

    def _fetch_input_settings(self, page_name: str) -> dict:
        """Fetch input settings (controller support) for a page."""
        result = {"has_controller": None}
        if not page_name:
            return result

        safe_name = page_name.replace('"', '\\"')
        response = self.get(self.BASE_URL, params={
            "action": "cargoquery",
            "tables": "Input",
            "fields": "Input.Controller=controller",
            "where": f'Input._pageName="{safe_name}"',
            "format": "json",
            "limit": "1",
        })
        if response.status_code != 200:
            return result

        data = response.json()
        rows = data.get("cargoquery", [])
        if not rows:
            return result

        row = rows[0].get("title", {})
        ctrl = row.get("controller", "")
        result["has_controller"] = ctrl.lower() == "true" if ctrl else None
        return result
