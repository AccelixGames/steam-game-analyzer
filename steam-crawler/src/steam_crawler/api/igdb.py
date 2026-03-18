"""IGDB API v4 client with Twitch OAuth authentication."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class IGDBClient:
    """IGDB API v4 client using composition (not BaseClient inheritance).

    IGDB uses POST requests with Apicalypse query language in the body.
    Authentication via Twitch OAuth client_credentials grant.
    """

    BASE_URL = "https://api.igdb.com/v4"
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
        """Auto-authenticate if token is missing or expiring within 60s."""
        if self._token is None or time.time() >= self._token_expires_at - 60:
            self.authenticate()

    def _post(self, endpoint: str, query: str) -> list[dict]:
        """POST an Apicalypse query to an IGDB endpoint with retry on 429/5xx."""
        self._ensure_auth()

        if self._rate_limiter:
            self._rate_limiter.wait()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._token}",
        }

        start = time.monotonic()
        response = self._http.post(url, content=query, headers=headers)
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
                    response = self._http.post(url, content=query, headers=headers)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if response.status_code < 400:
                        break
                if response.status_code == 429:
                    self._rate_limiter.record_rate_limited()
                elif response.status_code >= 500:
                    self._rate_limiter.record_server_error()
                else:
                    self._rate_limiter.record_success(elapsed_ms)
            else:
                self._rate_limiter.record_success(elapsed_ms)

        response.raise_for_status()
        return response.json()

    def search_by_steam_id(self, appid: int) -> dict | None:
        """Search IGDB for a game by Steam AppID via external_games endpoint.

        Two-step: 1) find game ID from external_games by uid,
                  2) fetch full game details by ID.
        """
        ext_query = f'fields game; where uid = "{appid}"; limit 1;'
        ext_results = self._post("external_games", ext_query)
        if not ext_results:
            return None
        game_id = ext_results[0].get("game")
        if not game_id:
            return None
        return self.fetch_game_details(game_id)

    def search_by_name(self, name: str) -> list[dict]:
        """Search IGDB for games by name. Returns list of candidates."""
        safe_name = name.replace('"', '\\"')
        query = (
            f'search "{safe_name}"; '
            f"fields name, summary, storyline, aggregated_rating, "
            f"themes.id, themes.name, keywords.id, keywords.name; "
            f"limit 10;"
        )
        return self._post("games", query)

    def fetch_game_details(self, igdb_id: int) -> dict | None:
        """Fetch full details for a specific IGDB game ID."""
        query = (
            f"fields name, summary, storyline, aggregated_rating, "
            f"themes.id, themes.name, keywords.id, keywords.name; "
            f"where id = {igdb_id}; limit 1;"
        )
        results = self._post("games", query)
        return results[0] if results else None

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
