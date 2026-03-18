"""analyze_design tool for steam-analyzer.

Compares a game design document against competitor reviews collected from
the Steam store, returning a structured summary of keyword trends and
representative review samples.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from steam_analyzer.db_queries import (
    get_games_by_tag,
    get_reviews_for_games,
    get_review_samples,
)
from steam_analyzer.error_logger import make_error_response
from steam_analyzer.stats.review_stats import compute_review_stats

_TOOL_NAME = "analyze_design"
_MAX_FILE_SIZE = 1024 * 1024  # 1 MB
_SAMPLE_LIMIT = 10


def handle_analyze_design(
    conn: sqlite3.Connection,
    design_file: str | None = None,
    design_text: str | None = None,
    tag: str | None = None,
    appids: list[int] | None = None,
) -> dict[str, Any]:
    """Analyze a game design against Steam competitor reviews.

    Parameters
    ----------
    conn:
        SQLite connection with row_factory set to sqlite3.Row.
    design_file:
        Path to a plain-text design document (max 1 MB).
    design_text:
        Raw design document text supplied directly.
    tag:
        Steam tag string used to resolve competitor appids.
    appids:
        Explicit list of competitor appids.

    Returns
    -------
    dict
        On success:
            design_content, competitor_summary, sample_reviews_positive,
            sample_reviews_negative.
        On failure:
            Structured error dict produced by make_error_response.
    """
    params: dict[str, Any] = {
        "design_file": design_file,
        "design_text": bool(design_text),
        "tag": tag,
        "appids": appids,
    }

    # ------------------------------------------------------------------
    # 1. Validate design input
    # ------------------------------------------------------------------
    if design_file is None and design_text is None:
        return make_error_response(
            conn,
            tool_name=_TOOL_NAME,
            params=params,
            error_type="no_data",
            error_message="Either design_file or design_text must be provided.",
            suggestion="Pass a design_text string or a path via design_file.",
        )

    # ------------------------------------------------------------------
    # 2. Validate competitor input
    # ------------------------------------------------------------------
    if tag is None and not appids:
        return make_error_response(
            conn,
            tool_name=_TOOL_NAME,
            params=params,
            error_type="no_data",
            error_message="Either tag or appids must be provided to identify competitors.",
            suggestion="Pass a tag name (e.g. 'Roguelike') or a list of appids.",
        )

    # ------------------------------------------------------------------
    # 3. Resolve design content
    # ------------------------------------------------------------------
    if design_file is not None:
        path = Path(design_file)

        if not path.exists():
            return make_error_response(
                conn,
                tool_name=_TOOL_NAME,
                params=params,
                error_type="file_error",
                error_message=f"Design file not found: {design_file}",
                suggestion="Check that the path is correct and the file exists.",
            )

        file_size = path.stat().st_size
        if file_size > _MAX_FILE_SIZE:
            return make_error_response(
                conn,
                tool_name=_TOOL_NAME,
                params=params,
                error_type="file_error",
                error_message=(
                    f"Design file is too large ({file_size} bytes). "
                    f"Maximum allowed size is {_MAX_FILE_SIZE} bytes (1 MB)."
                ),
                suggestion="Trim the design document to under 1 MB before passing it.",
            )

        design_content: str = path.read_text(encoding="utf-8", errors="replace")
    else:
        design_content = design_text  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # 4. Resolve competitor appids
    # ------------------------------------------------------------------
    if tag is not None:
        games = get_games_by_tag(conn, tag)
        competitor_appids = [g["appid"] for g in games]
    else:
        # appids were provided directly; look them up to count distinct games
        competitor_appids = list(appids)  # type: ignore[arg-type]

    games_count = len(competitor_appids)

    # ------------------------------------------------------------------
    # 5. Fetch reviews
    # ------------------------------------------------------------------
    reviews = get_reviews_for_games(conn, competitor_appids)

    # ------------------------------------------------------------------
    # 6. Compute stats
    # ------------------------------------------------------------------
    stats = compute_review_stats(reviews, top_n=30)

    # ------------------------------------------------------------------
    # 7. Fetch sample reviews (positive & negative, up to 10 each)
    # ------------------------------------------------------------------
    sample_positive = get_review_samples(
        conn, competitor_appids, voted_up=True, limit=_SAMPLE_LIMIT
    )
    sample_negative = get_review_samples(
        conn, competitor_appids, voted_up=False, limit=_SAMPLE_LIMIT
    )

    # ------------------------------------------------------------------
    # 8. Build and return response
    # ------------------------------------------------------------------
    return {
        "design_content": design_content,
        "competitor_summary": {
            "games_count": games_count,
            "positive_ratio": stats["positive_ratio"],
            "top_keywords_positive": stats["top_keywords_positive"],
            "top_keywords_negative": stats["top_keywords_negative"],
        },
        "sample_reviews_positive": sample_positive,
        "sample_reviews_negative": sample_negative,
    }
