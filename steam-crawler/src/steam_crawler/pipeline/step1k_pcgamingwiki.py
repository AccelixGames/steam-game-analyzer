"""Step 1k: Enrich games with PCGamingWiki technical data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.pcgamingwiki import PCGamingWikiClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_pcgamingwiki,
)

console = Console()


def run_step1k(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    pcgw_client: PCGamingWikiClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with PCGamingWiki technical data. Returns count enriched."""
    client = pcgw_client or PCGamingWikiClient(
        rate_limiter=AdaptiveRateLimiter(api_name="pcgamingwiki", default_delay_ms=1500)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="pcgamingwiki", source_tag=source_tag, lock_owner=lock_owner, appids=appids,
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1k: No games need PCGamingWiki enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1k:[/bold] Enriching {len(games)} games from PCGamingWiki")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.fetch_by_appid(appid)
                if data is None:
                    update_game_pcgamingwiki(conn, appid=appid, engine="unknown")
                    continue

                update_game_pcgamingwiki(
                    conn,
                    appid=appid,
                    engine=data.get("engine"),
                    has_ultrawide=data.get("has_ultrawide"),
                    has_hdr=data.get("has_hdr"),
                    has_controller=data.get("has_controller"),
                    graphics_api=data.get("graphics_api"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="pcgamingwiki",
                    appid=appid, step="step1k", error_message=str(e),
                )
                console.print(f"  [red]PCGamingWiki error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1k complete:[/green] {enriched}/{len(games)} games enriched from PCGamingWiki"
        )
        return enriched
    finally:
        if pcgw_client is None:
            client.close()
