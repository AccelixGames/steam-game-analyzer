"""Step 1f: Enrich games with Twitch streaming data (live channels, viewers)."""
from __future__ import annotations

import json
import sqlite3

from rich.console import Console

from steam_crawler.api.twitch import TwitchClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_twitch_stats,
)

console = Console()


def run_step1f(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    twitch_client: TwitchClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with Twitch streaming data. Returns count enriched."""
    if client_id is None and twitch_client is None:
        console.print("[yellow]Twitch credentials not set, skipping step 1f[/yellow]")
        return 0

    client = twitch_client or TwitchClient(
        client_id=client_id, client_secret=client_secret
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="twitch", source_tag=source_tag, lock_owner=lock_owner, appids=appids,
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1f: No games need Twitch enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1f:[/bold] Enriching {len(games)} games from Twitch")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                matched = client.search_game(name)
                if matched is None:
                    conn.execute(
                        "UPDATE games SET twitch_game_id='-1' WHERE appid=?",
                        (appid,),
                    )
                    conn.commit()
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="twitch",
                        appid=appid, step="step1f",
                        error_type="match_failed",
                        error_message=f"No Twitch category for '{name}'",
                    )
                    continue

                game_id = matched["id"]
                stats = client.get_live_stats(game_id)

                update_game_twitch_stats(
                    conn, appid=appid,
                    twitch_game_id=game_id,
                    stream_count=stats["stream_count"],
                    viewer_count=stats["viewer_count"],
                    top_language=stats["top_language"],
                    lang_distribution=json.dumps(
                        stats["lang_distribution"], ensure_ascii=False
                    ),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="twitch",
                    appid=appid, step="step1f", error_message=str(e),
                )
                console.print(
                    f"  [red]Twitch error for {name} ({appid}): {e}[/red]"
                )
                continue

        console.print(
            f"[green]Step 1f complete:[/green] {enriched}/{len(games)} games enriched from Twitch"
        )
        return enriched
    finally:
        if twitch_client is None:
            client.close()
