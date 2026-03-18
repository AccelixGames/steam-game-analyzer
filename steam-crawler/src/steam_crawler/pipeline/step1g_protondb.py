"""Step 1g: Enrich games with ProtonDB compatibility data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.protondb import ProtonDBClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_protondb,
)

console = Console()


def run_step1g(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    protondb_client: ProtonDBClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with ProtonDB compatibility tiers. Returns count enriched."""
    client = protondb_client or ProtonDBClient(
        rate_limiter=AdaptiveRateLimiter(api_name="protondb", default_delay_ms=1500)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="protondb", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1g: No games need ProtonDB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1g:[/bold] Enriching {len(games)} games from ProtonDB")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                data = client.fetch_summary(appid)
                if data is None:
                    update_game_protondb(conn, appid=appid, tier="unknown")
                    continue

                update_game_protondb(
                    conn,
                    appid=appid,
                    tier=data.get("tier", "unknown"),
                    confidence=data.get("confidence"),
                    trending_tier=data.get("trendingTier"),
                    report_count=data.get("total"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="protondb",
                    appid=appid, step="step1g", error_message=str(e),
                )
                console.print(f"  [red]ProtonDB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1g complete:[/green] {enriched}/{len(games)} games enriched from ProtonDB"
        )
        return enriched
    finally:
        if protondb_client is None:
            client.close()
