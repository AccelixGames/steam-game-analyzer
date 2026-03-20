"""Base HTTP client with rate limiting and TLS fingerprint impersonation."""

from __future__ import annotations

import time
from curl_cffi.requests import Session, Response

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


class BaseClient:
    def __init__(
        self,
        rate_limiter: AdaptiveRateLimiter | None = None,
        timeout: float = 10.0,
        impersonate: str = "chrome",
    ):
        self._client = Session(timeout=timeout, impersonate=impersonate)
        self._rate_limiter = rate_limiter

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> Response:
        """Make a GET request with rate limiting and retry on 429/5xx."""
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        response = self._client.get(url, params=params, headers=headers)
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
                    response = self._client.get(url, params=params, headers=headers)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if response.status_code < 400:
                        break
                # Record final result
                if response.status_code == 429:
                    self._rate_limiter.record_rate_limited()
                elif response.status_code >= 500:
                    self._rate_limiter.record_server_error()
                else:
                    self._rate_limiter.record_success(elapsed_ms)
            else:
                self._rate_limiter.record_success(elapsed_ms)

        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
