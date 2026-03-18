"""Twitch Helix API client for game streaming data."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class TwitchClient:
    """Twitch Helix API client. Shares Twitch OAuth with IGDB."""

    BASE_URL = "https://api.twitch.tv/helix"
    AUTH_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._rate_limiter = rate_limiter
        self._http = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_expires_at: float = 0

    def authenticate(self) -> None:
        """Obtain or refresh Twitch OAuth token."""
        response = self._http.post(
            self.AUTH_URL,
            params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]

    def _ensure_auth(self) -> None:
        if self._token is None or time.time() >= self._token_expires_at - 60:
            self.authenticate()

    def _get(self, endpoint: str, params: dict) -> dict:
        """GET request to Helix API with auth + rate limiting."""
        self._ensure_auth()
        if self._rate_limiter:
            self._rate_limiter.wait()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._token}",
        }

        start = time.monotonic()
        response = self._http.get(url, params=params, headers=headers)
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            if response.status_code == 429 or response.status_code >= 500:
                backoffs = self._rate_limiter.get_backoff_sequence()
                for delay_ms in backoffs:
                    if response.status_code == 429:
                        self._rate_limiter.record_rate_limited()
                    else:
                        self._rate_limiter.record_server_error()
                    time.sleep(delay_ms / 1000)
                    start = time.monotonic()
                    response = self._http.get(url, params=params, headers=headers)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if response.status_code < 400:
                        break
            else:
                self._rate_limiter.record_success(elapsed_ms)

        response.raise_for_status()
        return response.json()

    def search_game(self, name: str) -> dict | None:
        """Search Twitch categories by game name. Returns best match."""
        data = self._get("search/categories", {"query": name, "first": 5})
        results = data.get("data", [])
        name_lower = name.lower()
        for r in results:
            if r["name"].lower() == name_lower:
                return r
        return results[0] if results else None

    def get_live_stats(self, game_id: str, max_pages: int = 5) -> dict:
        """Get aggregated live streaming stats for a game.

        Returns dict with stream_count, viewer_count, top_language, lang_distribution.
        """
        all_streams = []
        cursor = None
        for _ in range(max_pages):
            params = {"game_id": game_id, "first": 100}
            if cursor:
                params["after"] = cursor
            data = self._get("streams", params)
            streams = data.get("data", [])
            if not streams:
                break
            all_streams.extend(streams)
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

        if not all_streams:
            return {
                "stream_count": 0,
                "viewer_count": 0,
                "top_language": None,
                "lang_distribution": {},
            }

        total_viewers = sum(s["viewer_count"] for s in all_streams)
        langs: dict[str, int] = {}
        for s in all_streams:
            lang = s["language"]
            langs[lang] = langs.get(lang, 0) + 1

        top_lang = max(langs, key=langs.get) if langs else None
        return {
            "stream_count": len(all_streams),
            "viewer_count": total_viewers,
            "top_language": top_lang,
            "lang_distribution": langs,
        }

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
