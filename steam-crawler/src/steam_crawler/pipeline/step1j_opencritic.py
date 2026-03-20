"""Step 1j: Enrich games with OpenCritic critic scores and reviews."""
from __future__ import annotations

import sqlite3

from rich.console import Console

from steam_crawler.api.opencritic import OpenCriticClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    get_games_needing_enrichment,
    update_game_opencritic,
    upsert_external_review,
)

console = Console()


def run_step1j(
    conn: sqlite3.Connection,
    version: int,
    source_tag: str | None = None,
    rapidapi_key: str | None = None,
    opencritic_client: OpenCriticClient | None = None,
    failure_tracker: FailureTracker | None = None,
    lock_owner: str | None = None,
    appids: list[int] | None = None,
) -> int:
    """Enrich games with OpenCritic scores + individual reviews. Returns count enriched."""
    if rapidapi_key is None and opencritic_client is None:
        console.print("[yellow]RAPIDAPI_KEY not set, skipping step 1j (OpenCritic)[/yellow]")
        return 0

    client = opencritic_client or OpenCriticClient(
        rapidapi_key=rapidapi_key,
        rate_limiter=AdaptiveRateLimiter(api_name="opencritic", default_delay_ms=3000),
    )
    tracker = failure_tracker or FailureTracker()
    games = get_games_needing_enrichment(
        conn, source="opencritic", source_tag=source_tag, lock_owner=lock_owner, appids=appids,
    )
    enriched = 0

    if not games:
        console.print("[dim]Step 1j: No games need OpenCritic enrichment[/dim]")
        return 0

    console.print(f"[bold]Step 1j:[/bold] Enriching {len(games)} games from OpenCritic")

    try:
        for game_row in games:
            appid = game_row["appid"]
            name = game_row["name"]
            try:
                matched = client.search(name)
                if matched is None:
                    update_game_opencritic(conn, appid=appid, opencritic_id=-1)
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="opencritic",
                        appid=appid, step="step1j",
                        error_type="match_failed",
                        error_message=f"No OpenCritic match for '{name}'",
                    )
                    continue

                oc_id = matched["id"]
                details = client.fetch_game(oc_id)
                if details is None:
                    update_game_opencritic(conn, appid=appid, opencritic_id=-1)
                    continue

                update_game_opencritic(
                    conn,
                    appid=appid,
                    opencritic_id=oc_id,
                    score=details.get("topCriticScore"),
                    pct_recommend=details.get("percentRecommended"),
                    tier=details.get("tier"),
                    review_count=details.get("numReviews"),
                )

                # Store individual critic reviews (optional, best-effort)
                try:
                    reviews = client.fetch_reviews(oc_id)
                    for rev in reviews[:10]:
                        outlets = rev.get("Outlet") or {}
                        authors = rev.get("Authors") or [{}]
                        upsert_external_review(
                            conn,
                            appid=appid,
                            source="opencritic",
                            source_id=str(rev.get("id", "")),
                            title=rev.get("title"),
                            score=rev.get("score"),
                            author=authors[0].get("name") if authors else None,
                            outlet=outlets.get("name"),
                            url=rev.get("externalUrl"),
                            snippet=rev.get("snippet"),
                            published_at=rev.get("publishedDate"),
                        )
                except Exception:
                    pass  # Individual reviews are optional

                enriched += 1

            except Exception as e:
                tracker.log_failure(
                    conn=conn, session_id=version, api_name="opencritic",
                    appid=appid, step="step1j", error_message=str(e),
                )
                console.print(f"  [red]OpenCritic error for {name} ({appid}): {e}[/red]")
                continue

        console.print(
            f"[green]Step 1j complete:[/green] {enriched}/{len(games)} games enriched from OpenCritic"
        )
        return enriched
    finally:
        if opencritic_client is None:
            client.close()
