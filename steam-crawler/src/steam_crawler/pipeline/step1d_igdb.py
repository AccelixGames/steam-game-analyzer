"""Step 1d: Enrich games with IGDB data (summary, storyline, themes, keywords)."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.igdb import IGDBClient
from steam_crawler.api.matching import GameMatcher
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_igdb_details,
    upsert_game_themes,
    upsert_game_keywords,
)

console = Console()


def run_step1d(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    igdb_client: IGDBClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
) -> int:
    """Enrich games with IGDB data. Returns count enriched."""
    if client_id is None and igdb_client is None:
        console.print("[yellow]IGDB credentials not set, skipping step 1d[/yellow]")
        return 0

    client = igdb_client or IGDBClient(client_id, client_secret)
    tracker = failure_tracker or FailureTracker()
    matcher = GameMatcher()
    games = get_games_needing_enrichment(conn, source="igdb", source_tag=source_tag, lock_owner=lock_owner)
    enriched = 0

    if not games:
        console.print("[dim]Step 1d: No games need IGDB enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1d:[/bold] Enriching {len(games)} games from IGDB")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                result = client.search_by_steam_id(appid)

                if result is None:
                    candidates = client.search_by_name(name)
                    matched = matcher.best_match(name, candidates)
                    if matched is None:
                        conn.execute(
                            "UPDATE games SET igdb_id=-1 WHERE appid=?", (appid,)
                        )
                        conn.commit()
                        tracker.log_failure(
                            conn=conn, session_id=version, api_name="igdb",
                            appid=appid, step="step1d",
                            error_type="match_failed",
                            error_message=f"No match for '{name}'",
                        )
                        continue
                    result = client.fetch_game_details(matched["id"])
                    if result is None:
                        continue

                igdb_id = result["id"]
                update_game_igdb_details(
                    conn, appid=appid, igdb_id=igdb_id,
                    igdb_summary=result.get("summary"),
                    igdb_storyline=result.get("storyline"),
                    igdb_rating=result.get("aggregated_rating"),
                )

                themes_raw = result.get("themes") or []
                if themes_raw:
                    themes = {t["id"]: t["name"] for t in themes_raw}
                    upsert_game_themes(conn, appid=appid, themes=themes)

                keywords_raw = result.get("keywords") or []
                if keywords_raw:
                    keywords = {k["id"]: k["name"] for k in keywords_raw}
                    upsert_game_keywords(conn, appid=appid, keywords=keywords)

                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="igdb",
                    appid=appid, step="step1d", error_message=str(e),
                )
                console.print(f"  [red]IGDB error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1d complete:[/green] {enriched}/{len(games)} games enriched from IGDB"
        )
        return enriched
    finally:
        if igdb_client is None:
            client.close()
