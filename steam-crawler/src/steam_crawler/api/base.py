"""Base HTTP client with rate limiting and failure tracking integration."""

from __future__ import annotations

import time
import httpx

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class BaseClient:
    def __init__(
        self,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
    ):
        self._client = httpx.Client(timeout=timeout)
        self._rate_limiter = rate_limiter

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        """Make a GET request with rate limiting."""
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        response = self._client.get(url, params=params)
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            if response.status_code == 429:
                self._rate_limiter.record_rate_limited()
            elif response.status_code >= 500:
                self._rate_limiter.record_server_error()
            else:
                self._rate_limiter.record_success(elapsed_ms)

        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
