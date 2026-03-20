"""Step 1l: Enrich games with Wikidata structured design data."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.wikidata import WikidataClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_wikidata,
    upsert_wikidata_claims,
)

console = Console()


def run_step1l(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    wikidata_client: WikidataClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with Wikidata claims. Returns count enriched."""
    client = wikidata_client or WikidataClient(
        rate_limiter=AdaptiveRateLimiter(api_name="wikidata", default_delay_ms=2000)
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="wikidata", source_tag=source_tag, lock_owner=lock_owner, appids=appids,
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1l: No games need Wikidata enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1l:[/bold] Enriching {len(games)} games from Wikidata")

    skipped = 0

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                result = client.fetch_by_steam_appid(appid)
                if result is None:
                    update_game_wikidata(conn, appid=appid, wikidata_id="not_found")
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="wikidata",
                        appid=appid, step="step1l",
                        error_type="empty_response",
                        error_message="No Wikidata entity or no design claims for this AppID",
                    )
                    console.print(f"  [dim]{name} ({appid}): not found on Wikidata[/dim]")
                    skipped += 1
                    continue

                update_game_wikidata(conn, appid=appid, wikidata_id=result["wikidata_id"])

                # Fill name_ko from Wikidata if Steam didn't provide one
                wikidata_name_ko = result.get("name_ko")
                if wikidata_name_ko:
                    existing_name_ko = conn.execute(
                        "SELECT name_ko FROM games WHERE appid = ?", (appid,)
                    ).fetchone()
                    if existing_name_ko and not existing_name_ko["name_ko"]:
                        conn.execute(
                            "UPDATE games SET name_ko = ? WHERE appid = ?",
                            (wikidata_name_ko, appid),
                        )
                        conn.commit()

                if result["claims"]:
                    upsert_wikidata_claims(conn, appid=appid, claims=result["claims"])

                claim_types = set(c["claim_type"] for c in result["claims"])
                ko_tag = f" [cyan]({wikidata_name_ko})[/cyan]" if wikidata_name_ko else ""
                console.print(
                    f"  [green]{name}[/green]{ko_tag}: {len(result['claims'])} claims "
                    f"({', '.join(sorted(claim_types))})"
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="wikidata",
                    appid=appid, step="step1l", error_message=str(e),
                )
                console.print(f"  [red]Wikidata error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1l complete:[/green] {enriched}/{len(games)} enriched, "
            f"{skipped} not found from Wikidata"
        )
        return enriched
    finally:
        if wikidata_client is None:
            client.close()
