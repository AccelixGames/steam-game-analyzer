"""Step 1: Collect game list from SteamSpy by tag/genre/top100."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.changelog import log_game_added, log_game_updated
from steam_crawler.db.repository import upsert_game

console = Console()


def run_step1(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None,
    limit: int,
    version: int,
    steamspy_client: SteamSpyClient | None = None,
) -> int:
    """Collect games from SteamSpy and upsert into DB.

    Returns number of games collected.
    """
    client = steamspy_client or SteamSpyClient()
    try:
        if query_type == "tag":
            games = client.fetch_by_tag(query_value, limit=limit)
        elif query_type == "genre":
            games = client.fetch_by_genre(query_value, limit=limit)
        elif query_type == "top100":
            games = client.fetch_top100(limit=limit)
        else:
            raise ValueError(f"Unknown query_type: {query_type}")

        for game in games:
            is_new, changes = upsert_game(conn, game, version=version)
            if is_new:
                log_game_added(conn, version=version, appid=game.appid)
            else:
                for field_name, (old_val, new_val) in changes.items():
                    log_game_updated(
                        conn,
                        version=version,
                        appid=game.appid,
                        field_name=field_name,
                        old_value=old_val,
                        new_value=new_val,
                    )

        console.print(f"[green]Step 1 complete:[/green] {len(games)} games collected")
        return len(games)
    finally:
        if steamspy_client is None:
            client.close()
