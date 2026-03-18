"""Review data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Review:
    recommendation_id: str
    appid: int
    language: str | None = None
    review_text: str | None = None
    voted_up: bool | None = None
    playtime_forever: int | None = None
    playtime_at_review: int | None = None
    early_access: bool | None = None
    steam_purchase: bool | None = None
    received_for_free: bool | None = None
    dev_response: str | None = None
    timestamp_created: int | None = None
    votes_up: int | None = None
    votes_funny: int | None = None
    weighted_vote_score: float | None = None
    comment_count: int | None = None
    author_steamid: str | None = None
    author_num_reviews: int | None = None
    author_playtime_forever: int | None = None

    @classmethod
    def from_steam_api(cls, data: dict[str, Any], appid: int) -> Review:
        author = data.get("author", {})
        wvs = data.get("weighted_vote_score")

        return cls(
            recommendation_id=data["recommendationid"],
            appid=appid,
            language=data.get("language"),
            review_text=data.get("review"),
            voted_up=data.get("voted_up"),
            playtime_forever=author.get("playtime_forever"),
            playtime_at_review=author.get("playtime_at_review"),
            early_access=data.get("written_during_early_access"),
            steam_purchase=data.get("steam_purchase"),
            received_for_free=data.get("received_for_free"),
            dev_response=data.get("developer_response"),
            timestamp_created=data.get("timestamp_created"),
            votes_up=data.get("votes_up"),
            votes_funny=data.get("votes_funny"),
            weighted_vote_score=float(wvs) if wvs is not None else None,
            comment_count=data.get("comment_count"),
            author_steamid=author.get("steamid"),
            author_num_reviews=author.get("num_reviews"),
            author_playtime_forever=author.get("playtime_forever"),
        )


@dataclass
class ReviewSummary:
    total_positive: int
    total_negative: int
    total_reviews: int
    review_score: int | None = None
    review_score_desc: str | None = None

    @classmethod
    def from_query_summary(cls, data: dict[str, Any]) -> ReviewSummary:
        return cls(
            total_positive=data["total_positive"],
            total_negative=data["total_negative"],
            total_reviews=data["total_reviews"],
            review_score=data.get("review_score"),
            review_score_desc=data.get("review_score_desc"),
        )
