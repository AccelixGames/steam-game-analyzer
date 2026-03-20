"""Step 1e: Enrich games with RAWG data (description, Metacritic score, rating)."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.matching import GameMatcher
from steam_crawler.api.rawg import RAWGClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_rawg_details,
)

console = Console()


def run_step1e(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    api_key: str | None = None,
    rawg_client: RAWGClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with RAWG data. Returns count enriched."""
    if api_key is None and rawg_client is None:
        console.print("[yellow]RAWG API key not set, skipping step 1e[/yellow]")
        return 0

    client = rawg_client or RAWGClient(api_key=api_key)
    tracker = failure_tracker or FailureTracker()
    matcher = GameMatcher()
    games = get_games_needing_enrichment(conn, source="rawg", source_tag=source_tag, lock_owner=lock_owner, appids=appids)
    enriched = 0

    if not games:
        console.print("[dim]Step 1e: No games need RAWG enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1e:[/bold] Enriching {len(games)} games from RAWG")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                candidates = client.search_by_name(name)
                matched = matcher.best_match(name, candidates)

                if matched is None:
                    conn.execute(
                        "UPDATE games SET rawg_id=-1 WHERE appid=?", (appid,)
                    )
                    conn.commit()
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="rawg",
                        appid=appid, step="step1e",
                        error_type="match_failed",
                        error_message=f"No match for '{name}'",
                    )
                    continue

                rawg_id = matched["id"]
                details = client.fetch_game_details(rawg_id)
                if details is None:
                    continue

                # Parse added_by_status (retention proxy)
                abs_data = details.get("added_by_status") or {}
                # Parse ratings (list of {id, title, count, percent})
                ratings_data = details.get("ratings") or []
                rating_pcts = {}
                for r in ratings_data:
                    title = r.get("title", "")
                    pct = r.get("percent", 0.0)
                    if title in ("exceptional", "recommended", "meh", "skip"):
                        rating_pcts[f"rawg_{title}_pct"] = pct

                update_game_rawg_details(
                    conn, appid=appid, rawg_id=rawg_id,
                    rawg_description=details.get("description_raw"),
                    rawg_rating=details.get("rating"),
                    metacritic_score=details.get("metacritic"),
                    rawg_ratings_count=details.get("ratings_count"),
                    rawg_added=details.get("added"),
                    rawg_status_yet=abs_data.get("yet"),
                    rawg_status_owned=abs_data.get("owned"),
                    rawg_status_beaten=abs_data.get("beaten"),
                    rawg_status_toplay=abs_data.get("toplay"),
                    rawg_status_dropped=abs_data.get("dropped"),
                    rawg_status_playing=abs_data.get("playing"),
                    rawg_exceptional_pct=rating_pcts.get("rawg_exceptional_pct"),
                    rawg_recommended_pct=rating_pcts.get("rawg_recommended_pct"),
                    rawg_meh_pct=rating_pcts.get("rawg_meh_pct"),
                    rawg_skip_pct=rating_pcts.get("rawg_skip_pct"),
                )
                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="rawg",
                    appid=appid, step="step1e", error_message=str(e),
                )
                console.print(f"  [red]RAWG error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1e complete:[/green] {enriched}/{len(games)} games enriched from RAWG"
        )
        return enriched
    finally:
        if rawg_client is None:
            client.close()
