"""Step 2: Scan review summaries from Steam Reviews API."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.db.changelog import log_reviews_count_changed
from steam_crawler.db.repository import (
    get_games_by_version,
    update_collection_status,
    update_game_review_stats,
)

console = Console()


def run_step2(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    reviews_client: SteamReviewsClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Scan review summaries for all games and update stats.

    Returns number of games scanned.
    """
    client = reviews_client or SteamReviewsClient()
    tracker = failure_tracker or FailureTracker()
    games = get_games_by_version(conn, source_tag=source_tag, lock_owner=lock_owner, appids=appids)
    scanned = 0
    try:
        for game_row in games:
            appid = game_row["appid"]
            try:
                summary = client.fetch_summary(appid)

                # Log SteamSpy vs Steam API deviation (info only, SteamSpy is estimates)
                spy_positive = game_row.get("positive")
                if spy_positive and spy_positive > 0:
                    deviation = abs(summary.total_positive - spy_positive) / spy_positive
                    if deviation > 0.5:
                        console.print(
                            f"  [dim]SteamSpy estimate differs: {spy_positive} vs "
                            f"Steam API {summary.total_positive} ({deviation:.0%})[/dim]"
                        )

                old_positive = game_row.get("steam_positive")
                update_game_review_stats(
                    conn,
                    appid=appid,
                    steam_positive=summary.total_positive,
                    steam_negative=summary.total_negative,
                    review_score=summary.review_score_desc,
                )
                if old_positive is not None and old_positive != summary.total_positive:
                    log_reviews_count_changed(
                        conn,
                        version=version,
                        appid=appid,
                        old_value=str(old_positive),
                        new_value=str(summary.total_positive),
                    )
                update_collection_status(
                    conn, appid=appid, version=version, summary_done=True
                )
                scanned += 1
            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="steam_reviews_summary",
                    appid=appid, step="step2", error_message=str(e),
                    error_type="connection_error" if isinstance(e, (ConnectionError, OSError)) else None,
                    http_status=getattr(e, 'response', {}).get('status_code') if hasattr(e, 'response') else None,
                )
                console.print(f"  [red]Error for appid={appid}: {e}[/red]")
                continue
        console.print(f"[green]Step 2 complete:[/green] {scanned} games scanned")
        return scanned
    finally:
        if reviews_client is None:
            client.close()
