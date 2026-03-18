"""Step 1c: Fetch store page details (description, images, videos) from Steam Store API."""
from __future__ import annotations

import sqlite3

import httpx
from rich.console import Console

from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steam_store import SteamStoreClient
from steam_crawler.db.repository import (
    get_games_by_version,
    update_collection_status,
    update_game_store_details,
    upsert_game_media,
)

console = Console()


def run_step1c(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    store_client: SteamStoreClient | None = None,
    failure_tracker: FailureTracker | None = None,
) -> int:
    """Fetch store details for games. Returns count enriched."""
    client = store_client or SteamStoreClient()
    tracker = failure_tracker or FailureTracker()
    games = get_games_by_version(conn, source_tag=source_tag)
    enriched = 0

    try:
        for game_row in games:
            appid = game_row["appid"]
            try:
                details = client.fetch_app_details(appid)
                if details is None:
                    continue

                update_game_store_details(
                    conn, appid=appid,
                    short_description=details.short_description,
                    header_image=details.header_image,
                )

                for media in details.media:
                    upsert_game_media(
                        conn, appid=appid,
                        media_type=media.media_type,
                        media_id=media.media_id,
                        name=media.name,
                        url_thumbnail=media.url_thumbnail,
                        url_full=media.url_full,
                    )

                enriched += 1
            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="steam_store",
                    appid=appid, step="step1c", error_message=str(e),
                    error_type="connection_error" if isinstance(e, httpx.ConnectError) else None,
                )
                console.print(f"  [red]Error for appid={appid}: {e}[/red]")
                continue

        console.print(
            f"[green]Step 1c complete:[/green] {enriched}/{len(games)} games enriched with store details"
        )
        return enriched
    finally:
        if store_client is None:
            client.close()
