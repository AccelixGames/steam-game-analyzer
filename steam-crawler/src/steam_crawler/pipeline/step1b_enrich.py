"""Step 1.5: Enrich games with SteamSpy appdetails (tags field)."""
from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.repository import get_games_by_version, update_collection_status

console = Console()


def run_step1b(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    steamspy_client: SteamSpyClient | None = None,
) -> int:
    """Enrich games with detailed tag data from SteamSpy appdetails.

    Returns number of games enriched.
    """
    client = steamspy_client or SteamSpyClient()
    games = get_games_by_version(conn, source_tag=source_tag)
    enriched = 0
    try:
        for game_row in games:
            appid = game_row["appid"]
            detail = client.fetch_app_details(appid)
            if detail.tags:
                tags_json = json.dumps(detail.tags)
                conn.execute(
                    "UPDATE games SET tags = ? WHERE appid = ?", (tags_json, appid)
                )
                conn.commit()
                enriched += 1
            update_collection_status(
                conn, appid=appid, version=version, steamspy_done=True
            )
        console.print(
            f"[green]Step 1.5 complete:[/green] {enriched}/{len(games)} games enriched with tags"
        )
        return enriched
    finally:
        if steamspy_client is None:
            client.close()
