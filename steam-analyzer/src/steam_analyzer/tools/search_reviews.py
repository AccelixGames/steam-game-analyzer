"""search_reviews MCP tool implementation."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from steam_analyzer.db_queries import (
    get_available_tags,
    get_games_by_tag,
    get_review_samples,
    get_reviews_for_games,
)
from steam_analyzer.error_logger import make_error_response
from steam_analyzer.stats.review_stats import compute_review_stats

_TOOL_NAME = "search_reviews"
_DEFAULT_SAMPLE_COUNT = 20
_MAX_SAMPLE_COUNT = 50


def handle_search_reviews(
    conn: sqlite3.Connection,
    tag: Optional[str] = None,
    appid: Optional[int] = None,
    language: Optional[str] = None,
    sample_count: Optional[int] = None,
) -> dict[str, Any]:
    """Search and analyse Steam reviews filtered by tag or appid.

    Parameters
    ----------
    conn:
        SQLite connection with ``row_factory = sqlite3.Row`` already set.
    tag:
        Tag name to filter games (e.g. "Roguelike").
    appid:
        Specific Steam appid to look up.
    language:
        Optional language filter passed through to review queries.
    sample_count:
        Maximum number of sample reviews to return (default 20, capped at 50).

    Returns
    -------
    dict
        On success:
            games_count, total_reviews, positive_ratio,
            top_keywords_positive, top_keywords_negative, sample_reviews
        On error (no tag/appid supplied):
            error, error_id, error_type, error_message, suggestion
        When no games found:
            games_count=0, empty arrays, available_tags
    """
    # --- 1. Validate input ---
    if tag is None and appid is None:
        return make_error_response(
            conn=conn,
            tool_name=_TOOL_NAME,
            params={"tag": tag, "appid": appid, "language": language, "sample_count": sample_count},
            error_type="no_data",
            error_message="Either 'tag' or 'appid' must be provided.",
            suggestion="Provide a tag name (e.g. tag='Roguelike') or a specific appid.",
        )

    # --- 2. Normalise sample_count ---
    if sample_count is None:
        sample_count = _DEFAULT_SAMPLE_COUNT
    sample_count = min(sample_count, _MAX_SAMPLE_COUNT)

    # --- 3. Resolve games ---
    if tag is not None:
        games = get_games_by_tag(conn, tag)
    else:
        # appid path — query games table directly
        row = conn.execute(
            "SELECT * FROM games WHERE appid = ?", (appid,)
        ).fetchone()
        games = [dict(row)] if row is not None else []

    appids: list[int] = [g["appid"] for g in games]

    # --- 4. Handle no games found ---
    if not appids:
        available_tags = get_available_tags(conn)
        return {
            "games_count": 0,
            "total_reviews": 0,
            "positive_ratio": 0.0,
            "top_keywords_positive": [],
            "top_keywords_negative": [],
            "sample_reviews": [],
            "available_tags": available_tags,
        }

    # --- 5. Fetch all reviews (for stats) ---
    reviews = get_reviews_for_games(conn, appids, language=language)

    # --- 6. Compute stats ---
    stats = compute_review_stats(reviews, top_n=30)

    # --- 7. Build sample reviews ---
    half = max(sample_count // 2, 1)
    positive_samples = get_review_samples(conn, appids, voted_up=True, limit=half, language=language)
    negative_samples = get_review_samples(conn, appids, voted_up=False, limit=half, language=language)

    combined = positive_samples + negative_samples
    combined.sort(key=lambda r: r.get("weighted_vote_score", 0.0), reverse=True)
    sample_reviews = combined[:sample_count]

    return {
        "games_count": len(games),
        "total_reviews": stats["total_reviews"],
        "positive_ratio": stats["positive_ratio"],
        "top_keywords_positive": stats["top_keywords_positive"],
        "top_keywords_negative": stats["top_keywords_negative"],
        "sample_reviews": sample_reviews,
    }
