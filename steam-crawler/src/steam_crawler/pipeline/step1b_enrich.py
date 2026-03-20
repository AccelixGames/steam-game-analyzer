"""Step 1.5: Enrich games with SteamSpy appdetails (tags field)."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.repository import get_games_by_version, update_collection_status, upsert_game_genres, upsert_game_tags

console = Console()


def run_step1b(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    steamspy_client: SteamSpyClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with detailed tag data from SteamSpy appdetails.

    Returns number of games enriched.
    """
    client = steamspy_client or SteamSpyClient()
    tracker = failure_tracker or FailureTracker()
    games = get_games_by_version(conn, source_tag=source_tag, lock_owner=lock_owner, appids=appids)
    enriched = 0
    try:
        for game_row in games:
            appid = game_row["appid"]
            try:
                detail = client.fetch_app_details(appid)
                if detail.tags:
                    upsert_game_tags(conn, appid, detail.tags)
                if detail.genres:
                    upsert_game_genres(conn, appid, detail.genres)
                if detail.tags or detail.genres:
                    enriched += 1
                update_collection_status(
                    conn, appid=appid, version=version, steamspy_done=True
                )
            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="steamspy_appdetails",
                    appid=appid, step="step1b", error_message=str(e),
                    error_type="connection_error" if isinstance(e, (ConnectionError, OSError)) else None,
                    http_status=getattr(e, 'response', {}).get('status_code') if hasattr(e, 'response') else None,
                )
                console.print(f"  [red]Error for appid={appid}: {e}[/red]")
                continue
        console.print(
            f"[green]Step 1.5 complete:[/green] {enriched}/{len(games)} games enriched with tags"
        )
        return enriched
    finally:
        if steamspy_client is None:
            client.close()
