"""Step 3: Crawl review text from Steam Reviews API.

Two-phase collection strategy:
  Phase 1 (filter=all):   1 page of most-helpful reviews (~80)
  Phase 2 (filter=recent): remaining up to max_reviews, with cursor resume
"""
from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.changelog import log_reviews_batch_added
from steam_crawler.db.repository import (
    get_games_by_version,
    insert_reviews_batch,
    update_collection_status,
)

console = Console()


def _count_reviews(conn: sqlite3.Connection, appid: int) -> int:
    """Count actual unique reviews in DB for a game."""
    row = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE appid = ?", (appid,)
    ).fetchone()
    return row[0] if row else 0


def _reset_undercollected(
    conn: sqlite3.Connection, version: int, max_reviews: int
) -> int:
    """Reset reviews_done for games that haven't reached max_reviews yet."""
    cur = conn.execute(
        """UPDATE game_collection_status
           SET reviews_done = 0, last_cursor = NULL
           WHERE version = ? AND reviews_done = 1 AND reviews_collected < ?""",
        (version, max_reviews),
    )
    conn.commit()
    return cur.rowcount


def run_step3(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    top_n: int = 10,
    max_reviews: int = 1000,
    language: str = "all",
    review_type: str = "all",
    reviews_client: SteamReviewsClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Crawl review text for top N games.

    If *appids* is given, only those games are targeted (ignoring top_n).
    Returns total number of reviews collected.
    """
    client = reviews_client or SteamReviewsClient()
    tracker = failure_tracker or FailureTracker()
    all_games = get_games_by_version(conn, source_tag=source_tag, lock_owner=lock_owner)
    if appids is not None:
        target_set = set(appids)
        games = [g for g in all_games if g["appid"] in target_set]
    else:
        games = all_games[:top_n]

    # Backfill: reset games that were "done" under old threshold
    reset_count = _reset_undercollected(conn, version, max_reviews)
    if reset_count > 0:
        console.print(
            f"[yellow]Backfill: {reset_count} games reset for additional collection[/yellow]"
        )

    total_collected = 0
    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                status = conn.execute(
                    "SELECT * FROM game_collection_status WHERE appid=? AND version=?",
                    (appid, version),
                ).fetchone()
                if status and status["reviews_done"]:
                    continue

                # Populate reviews_total from games table
                row = conn.execute(
                    "SELECT COALESCE(steam_positive, 0) + COALESCE(steam_negative, 0) FROM games WHERE appid = ?",
                    (appid,),
                ).fetchone()
                reviews_total = row[0] if row else 0
                if reviews_total > 0:
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_total=reviews_total,
                    )

                # Effective cap: don't try to collect more than what exists
                effective_max = min(max_reviews, reviews_total) if reviews_total > 0 else max_reviews
                actual_count = _count_reviews(conn, appid)

                if actual_count >= effective_max:
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_done=True, reviews_collected=actual_count,
                    )
                    continue

                console.print(
                    f"[blue]Crawling reviews for {name} (appid={appid})...[/blue]"
                )

                # ── Phase 1: filter=all (most helpful, 1 page) ──
                all_reviews, _, _ = client.fetch_reviews_page(
                    appid=appid, cursor="*",
                    language=language, review_type=review_type,
                    review_filter="all",
                )
                if all_reviews:
                    insert_reviews_batch(conn, all_reviews, version=version)
                    actual_count = _count_reviews(conn, appid)
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_collected=actual_count,
                    )
                    console.print(f"  Phase 1 (helpful): {len(all_reviews)} fetched, {actual_count} unique total")

                # ── Phase 2: filter=recent (cursor-resumable) ──
                cursor = status["last_cursor"] if status and status["last_cursor"] else "*"
                has_more = True

                while actual_count < effective_max and has_more:
                    reviews, next_cursor, has_more = client.fetch_reviews_page(
                        appid=appid, cursor=cursor,
                        language=language, review_type=review_type,
                        review_filter="recent",
                    )
                    if not reviews:
                        has_more = False
                        break
                    insert_reviews_batch(conn, reviews, version=version)
                    actual_count = _count_reviews(conn, appid)
                    total_collected = actual_count
                    update_collection_status(
                        conn, appid=appid, version=version,
                        last_cursor=next_cursor,
                        reviews_collected=actual_count,
                    )
                    cursor = next_cursor

                is_done = actual_count >= effective_max or not has_more
                if is_done:
                    update_collection_status(
                        conn, appid=appid, version=version,
                        reviews_done=True,
                        languages_done=json.dumps([language]),
                        review_types_done=json.dumps([review_type]),
                    )
                if actual_count > 0:
                    log_reviews_batch_added(
                        conn, version=version, appid=appid, count=actual_count
                    )
                console.print(f"  -> {actual_count} reviews total ({effective_max} target)")
            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="steam_reviews_crawl",
                    appid=appid, step="step3", error_message=str(e),
                    error_type="connection_error" if isinstance(e, (ConnectionError, OSError)) else None,
                    http_status=getattr(e, 'response', {}).get('status_code') if hasattr(e, 'response') else None,
                )
                console.print(f"  [red]Error for appid={appid}: {e}[/red]")
                continue

        console.print(f"[green]Step 3 complete:[/green] {total_collected} total reviews")
        return total_collected
    finally:
        if reviews_client is None:
            client.close()
