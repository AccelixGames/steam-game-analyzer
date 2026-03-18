"""Step 3: Crawl review text from Steam Reviews API."""
from __future__ import annotations

import json
import sqlite3

import httpx
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


def run_step3(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    top_n: int = 10,
    max_reviews: int = 500,
    language: str = "all",
    review_type: str = "all",
    reviews_client: SteamReviewsClient | None = None,
    failure_tracker: FailureTracker | None = None,
) -> int:
    """Crawl review text for top N games.

    Returns total number of reviews collected.
    """
    client = reviews_client or SteamReviewsClient()
    tracker = failure_tracker or FailureTracker()
    games = get_games_by_version(conn, source_tag=source_tag)[:top_n]
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

                cursor = status["last_cursor"] if status and status["last_cursor"] else "*"
                collected_for_game = status["reviews_collected"] if status else 0
                has_more = True

                console.print(
                    f"[blue]Crawling reviews for {name} (appid={appid})...[/blue]"
                )

                while collected_for_game < max_reviews and has_more:
                    reviews, next_cursor, has_more = client.fetch_reviews_page(
                        appid=appid,
                        cursor=cursor,
                        language=language,
                        review_type=review_type,
                    )
                    if not reviews:
                        has_more = False
                        break
                    inserted = insert_reviews_batch(conn, reviews, version=version)
                    collected_for_game += inserted
                    total_collected += inserted
                    update_collection_status(
                        conn,
                        appid=appid,
                        version=version,
                        last_cursor=next_cursor,
                        reviews_collected=collected_for_game,
                    )
                    cursor = next_cursor

                is_done = collected_for_game >= max_reviews or not has_more
                if is_done:
                    update_collection_status(
                        conn,
                        appid=appid,
                        version=version,
                        reviews_done=True,
                        languages_done=json.dumps([language]),
                        review_types_done=json.dumps([review_type]),
                    )
                if collected_for_game > 0:
                    log_reviews_batch_added(
                        conn, version=version, appid=appid, count=collected_for_game
                    )
                console.print(f"  -> {collected_for_game} reviews collected")
            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="steam_reviews_crawl",
                    appid=appid, step="step3", error_message=str(e),
                    error_type="connection_error" if isinstance(e, httpx.ConnectError) else None,
                    http_status=getattr(e, 'response', {}).get('status_code') if hasattr(e, 'response') else None,
                )
                console.print(f"  [red]Error for appid={appid}: {e}[/red]")
                continue

        console.print(f"[green]Step 3 complete:[/green] {total_collected} total reviews")
        return total_collected
    finally:
        if reviews_client is None:
            client.close()
