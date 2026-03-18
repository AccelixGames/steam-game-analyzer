"""Steam Store Reviews API client."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.models.review import Review, ReviewSummary

REVIEWS_BASE = "https://store.steampowered.com/appreviews"


class SteamReviewsClient:
    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        self._client = BaseClient(
            rate_limiter=rate_limiter or AdaptiveRateLimiter(
                api_name="steam_reviews", default_delay_ms=1500,
            ),
        )

    def fetch_summary(self, appid: int) -> ReviewSummary:
        response = self._client.get(
            f"{REVIEWS_BASE}/{appid}",
            params={"json": "1", "cursor": "*", "filter": "recent",
                    "purchase_type": "all", "num_per_page": "0"},
        )
        response.raise_for_status()
        data = response.json()
        return ReviewSummary.from_query_summary(data["query_summary"])

    def fetch_reviews_page(
        self, appid: int, cursor: str = "*",
        language: str = "all", review_type: str = "all",
    ) -> tuple[list[Review], str, bool]:
        response = self._client.get(
            f"{REVIEWS_BASE}/{appid}",
            params={"json": "1", "cursor": cursor, "filter": "recent",
                    "purchase_type": "all", "num_per_page": "80",
                    "language": language, "review_type": review_type},
        )
        response.raise_for_status()
        data = response.json()
        reviews_data = data.get("reviews", [])
        reviews = [Review.from_steam_api(r, appid=appid) for r in reviews_data]
        next_cursor = data.get("cursor", "")
        has_more = len(reviews_data) > 0
        return reviews, next_cursor, has_more

    def close(self):
        self._client.close()
