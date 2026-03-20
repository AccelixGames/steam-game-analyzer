"""HowLongToBeat wrapper — game completion time data."""

from __future__ import annotations

import asyncio
import concurrent.futures
import time

from howlongtobeatpy import HowLongToBeat

from steam_crawler.api.rate_limiter import AdaptiveRateLimiter


def _run_async(coro):
    """Run an async coroutine from sync code, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class HLTBClient:
    """Wrapper around howlongtobeatpy with rate limiting."""

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._rate_limiter = rate_limiter

    def search(self, game_name: str) -> dict | None:
        """Search HowLongToBeat by game name. Returns best match or None.
        Times are in hours (float).
        """
        if self._rate_limiter:
            self._rate_limiter.wait()

        start = time.monotonic()
        results = _run_async(HowLongToBeat().async_search(game_name))
        elapsed_ms = (time.monotonic() - start) * 1000

        if self._rate_limiter:
            self._rate_limiter.record_success(elapsed_ms)

        if not results:
            return None

        best = max(results, key=lambda r: r.similarity)
        if best.similarity < 0.4:
            return None

        return {
            "game_id": best.game_id,
            "main_story": best.main_story if best.main_story > 0 else None,
            "main_extra": best.main_extra if best.main_extra > 0 else None,
            "completionist": best.completionist if best.completionist > 0 else None,
        }

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
