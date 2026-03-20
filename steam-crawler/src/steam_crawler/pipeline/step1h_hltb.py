"""Step 1h: Enrich games with HowLongToBeat completion times."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.hltb import HLTBClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_hltb,
)

console = Console()


def run_step1h(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    hltb_client: HLTBClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with HowLongToBeat completion times. Returns count enriched."""
    client = hltb_client or HLTBClient(
        rate_limiter=AdaptiveRateLimiter(api_name="hltb", default_delay_ms=2000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="hltb", source_tag=source_tag, lock_owner=lock_owner, appids=appids,
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1h: No games need HLTB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1h:[/bold] Enriching {len(games)} games from HowLongToBeat")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.search(name)
                if data is None:
                    update_game_hltb(conn, appid=appid, hltb_id=-1)
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="hltb",
                        appid=appid, step="step1h",
                        error_type="match_failed",
                        error_message=f"No HLTB match for '{name}'",
                    )
                    continue

                update_game_hltb(
                    conn,
                    appid=appid,
                    hltb_id=data["game_id"],
                    main_story=data["main_story"],
                    main_extra=data["main_extra"],
                    completionist=data["completionist"],
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="hltb",
                    appid=appid, step="step1h", error_message=str(e),
                )
                console.print(f"  [red]HLTB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1h complete:[/green] {enriched}/{len(games)} games enriched from HLTB"
        )
        return enriched
    finally:
        if hltb_client is None:
            client.close()
