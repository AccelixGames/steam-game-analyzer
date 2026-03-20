"""Step 1i: Enrich games with CheapShark deal/price data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.cheapshark import CheapSharkClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_cheapshark,
)

console = Console()


def run_step1i(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    cheapshark_client: CheapSharkClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with CheapShark deal ratings. Returns count enriched."""
    client = cheapshark_client or CheapSharkClient(
        rate_limiter=AdaptiveRateLimiter(api_name="cheapshark", default_delay_ms=1000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="cheapshark", source_tag=source_tag, lock_owner=lock_owner
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1i: No games need CheapShark enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1i:[/bold] Enriching {len(games)} games from CheapShark")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                deal = client.search_by_steam_appid(appid)
                if deal is None:
                    update_game_cheapshark(conn, appid=appid, deal_rating=0.0)
                    continue

                deal_rating = float(deal.get("dealRating", 0))
                lowest_price = None
                lowest_price_date = None

                game_id = deal.get("gameID")
                if game_id:
                    details = client.fetch_game_details(game_id)
                    if details and "cheapestPriceEver" in details:
                        cpe = details["cheapestPriceEver"]
                        lowest_price = float(cpe.get("price", 0))
                        lowest_price_date = cpe.get("date")

                update_game_cheapshark(
                    conn,
                    appid=appid,
                    deal_rating=deal_rating,
                    lowest_price=lowest_price,
                    lowest_price_date=lowest_price_date,
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="cheapshark",
                    appid=appid, step="step1i", error_message=str(e),
                )
                console.print(f"  [red]CheapShark error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1i complete:[/green] {enriched}/{len(games)} games enriched from CheapShark"
        )
        return enriched
    finally:
        if cheapshark_client is None:
            client.close()
