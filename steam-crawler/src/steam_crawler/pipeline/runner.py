"""Pipeline orchestrator -- runs steps in sequence with resilience."""
from __future__ import annotations

import json
import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console

from steam_crawler.api.rate_limiter import (
    AdaptiveRateLimiter,
    load_optimal_delay,
    save_rate_stats,
)
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.api.steam_store import SteamStoreClient
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.db.repository import (
    acquire_crawl_lock,
    cleanup_expired_locks,
    create_version,
    get_games_by_version,
    release_crawl_lock,
    update_version_status,
    validate_source_tags,
)
from steam_crawler.pipeline.step1_collect import run_step1
from steam_crawler.pipeline.step1b_enrich import run_step1b
from steam_crawler.pipeline.step1c_store import run_step1c
from steam_crawler.pipeline.step1d_igdb import run_step1d
from steam_crawler.pipeline.step1e_rawg import run_step1e
from steam_crawler.pipeline.step1f_twitch import run_step1f
from steam_crawler.pipeline.step1g_protondb import run_step1g
from steam_crawler.pipeline.step1h_hltb import run_step1h
from steam_crawler.pipeline.step1i_cheapshark import run_step1i
from steam_crawler.pipeline.step1j_opencritic import run_step1j
from steam_crawler.pipeline.step1k_pcgamingwiki import run_step1k
from steam_crawler.pipeline.step2_scan import run_step2
from steam_crawler.pipeline.step3_crawl import run_step3

console = Console()


def build_source_tag(query_type: str, query_value: str | None) -> str | None:
    """Build a source_tag string from query parameters."""
    if query_type == "top100":
        return "top100"
    return f"{query_type}:{query_value}" if query_value else None


def run_pipeline(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None = None,
    limit: int = 50,
    top_n: int = 10,
    max_reviews: int = 500,
    language: str = "all",
    review_type: str = "all",
    step: int | None = None,
    resume: bool = False,
    note: str | None = None,
) -> None:
    """Run the full pipeline or a single step.

    Args:
        conn: Database connection.
        query_type: One of "tag", "genre", "top100".
        query_value: The tag/genre name (not needed for top100).
        limit: Max games to collect in step 1.
        top_n: Number of top games to crawl reviews for in step 3.
        max_reviews: Max reviews per game in step 3.
        language: Language filter for reviews.
        review_type: Review type filter.
        step: If set, only run this step (1, 2, or 3).
        resume: If True, resume the last interrupted version.
        note: Optional note for the version.
    """
    tracker = FailureTracker()

    unresolved = tracker.get_unresolved(conn)
    if unresolved:
        console.print(
            f"[yellow]Warning: {len(unresolved)} unresolved failures from previous sessions[/yellow]"
        )
        if tracker.check_schema_change_risk(conn):
            console.print(
                "[red]Warning: Multiple parse errors detected -- API schema may have changed[/red]"
            )

    spy_delay = load_optimal_delay(conn, "steamspy") or 1000
    rev_delay = load_optimal_delay(conn, "steam_reviews") or 1500
    store_delay = load_optimal_delay(conn, "steam_store") or 1500
    spy_limiter = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=spy_delay)
    rev_limiter = AdaptiveRateLimiter(
        api_name="steam_reviews", default_delay_ms=rev_delay
    )
    store_limiter = AdaptiveRateLimiter(api_name="steam_store", default_delay_ms=store_delay)
    spy_client = SteamSpyClient(rate_limiter=spy_limiter)
    rev_client = SteamReviewsClient(rate_limiter=rev_limiter)
    store_client = SteamStoreClient(rate_limiter=store_limiter)

    # Resume: find last interrupted version
    if resume:
        row = conn.execute(
            "SELECT version, config FROM data_versions WHERE status='interrupted' ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            console.print(
                "[yellow]No interrupted version found. Starting fresh.[/yellow]"
            )
            resume = False
        else:
            version = row["version"]
            cfg = json.loads(row["config"]) if row["config"] else {}
            query_type = cfg.get("query_type", query_type)
            query_value = cfg.get("query_value", query_value)
            conn.execute(
                "UPDATE data_versions SET status='running' WHERE version=?",
                (version,),
            )
            conn.commit()
            console.print(f"[bold]Resuming pipeline v{version}[/bold]")

    if not resume:
        config = json.dumps(
            {
                "query_type": query_type,
                "query_value": query_value,
                "limit": limit,
                "top_n": top_n,
                "max_reviews": max_reviews,
                "language": language,
                "review_type": review_type,
            }
        )
        version = create_version(
            conn, query_type, query_value, config=config, note=note
        )

    source_tag = build_source_tag(query_type, query_value)
    lock_owner = f"pipeline:{version}"
    console.print(
        f"[bold]Pipeline v{version} started[/bold] ({query_type}:{query_value or ''})"
    )

    # Clean up any expired locks from crashed sessions
    expired = cleanup_expired_locks(conn)
    if expired:
        console.print(f"[dim]Cleaned up {expired} expired crawl lock(s)[/dim]")

    games_total = 0
    reviews_total = 0
    locked_appids: list[int] = []

    try:
        if step is None or step == 1:
            games_total = run_step1(
                conn,
                query_type,
                query_value,
                limit,
                version,
                steamspy_client=spy_client,
            )

            # Acquire per-game locks after step1 discovers games
            all_games = get_games_by_version(conn, source_tag=source_tag)
            skipped = 0
            for g in all_games:
                if acquire_crawl_lock(conn, g["appid"], owner=lock_owner):
                    locked_appids.append(g["appid"])
                else:
                    skipped += 1
            if skipped:
                console.print(
                    f"[yellow]{skipped} game(s) skipped — already being crawled by another process[/yellow]"
                )

            run_step1b(
                conn, version, source_tag=source_tag, steamspy_client=spy_client,
                lock_owner=lock_owner,
            )

            # Validate source_tag against actual tags after enrichment
            mismatched = validate_source_tags(conn, source_tag=source_tag)
            if mismatched:
                console.print(
                    f"[yellow]Source tag validation: {len(mismatched)} games don't match '{source_tag}'[/yellow]"
                )
                for g in mismatched:
                    tracker.log_failure(
                        conn=conn, session_id=version, api_name="source_tag_validation",
                        appid=g["appid"], step="step1b_validate",
                        error_type="data_quality",
                        error_message=f"Game '{g['name']}' lacks expected tag from {source_tag}",
                    )
                    console.print(f"  [dim]- {g['name']} (appid={g['appid']})[/dim]")

            run_step1c(
                conn, version, source_tag=source_tag, store_client=store_client,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1d: IGDB enrichment (optional, needs env vars)
            igdb_cid = os.environ.get("TWITCH_CLIENT_ID") or None
            igdb_csec = os.environ.get("TWITCH_CLIENT_SECRET") or None
            run_step1d(
                conn, version, source_tag=source_tag,
                client_id=igdb_cid, client_secret=igdb_csec,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1e: RAWG enrichment (optional, needs env var)
            rawg_key = os.environ.get("RAWG_API_KEY") or None
            run_step1e(
                conn, version, source_tag=source_tag,
                api_key=rawg_key,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1f: Twitch streaming data (optional, uses same Twitch creds as IGDB)
            run_step1f(
                conn, version, source_tag=source_tag,
                client_id=igdb_cid, client_secret=igdb_csec,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1g: ProtonDB compatibility (no auth needed)
            run_step1g(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1h: HowLongToBeat completion times (no auth needed)
            run_step1h(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1i: CheapShark deal/price data (no auth needed)
            run_step1i(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1j: OpenCritic critic scores (optional, needs RAPIDAPI_KEY)
            rapidapi_key = os.environ.get("RAPIDAPI_KEY") or None
            run_step1j(
                conn, version, source_tag=source_tag,
                rapidapi_key=rapidapi_key,
                failure_tracker=tracker, lock_owner=lock_owner,
            )

            # Step 1k: PCGamingWiki technical data (no auth needed)
            run_step1k(
                conn, version, source_tag=source_tag,
                failure_tracker=tracker, lock_owner=lock_owner,
            )
        if step is None or step == 2:
            run_step2(
                conn,
                version,
                source_tag=source_tag,
                reviews_client=rev_client,
                failure_tracker=tracker,
                lock_owner=lock_owner,
            )
        if step is None or step == 3:
            reviews_total = run_step3(
                conn,
                version,
                source_tag=source_tag,
                top_n=top_n,
                max_reviews=max_reviews,
                language=language,
                review_type=review_type,
                reviews_client=rev_client,
                lock_owner=lock_owner,
            )

        update_version_status(
            conn,
            version,
            "completed",
            games_total=games_total,
            reviews_total=reviews_total,
        )
        console.print(f"[bold green]Pipeline v{version} completed[/bold green]")

    except KeyboardInterrupt:
        update_version_status(
            conn,
            version,
            "interrupted",
            games_total=games_total,
            reviews_total=reviews_total,
        )
        console.print(
            f"\n[yellow]Pipeline v{version} interrupted. Use --resume to continue.[/yellow]"
        )
    except Exception as e:
        update_version_status(
            conn,
            version,
            "interrupted",
            games_total=games_total,
            reviews_total=reviews_total,
        )
        console.print(f"[red]Pipeline v{version} failed: {e}[/red]")
        raise
    finally:
        # Release all locks held by this pipeline
        for appid in locked_appids:
            release_crawl_lock(conn, appid)

        save_rate_stats(conn, spy_limiter, session_id=version)
        save_rate_stats(conn, rev_limiter, session_id=version)
        save_rate_stats(conn, store_limiter, session_id=version)

        summary = tracker.get_session_summary(conn, session_id=version)
        if summary["total"] > 0:
            console.print(
                f"\n[yellow]Failure summary: {summary['total']} total, {summary['resolved']} resolved[/yellow]"
            )
            for ftype, count in summary["by_type"].items():
                console.print(f"  {ftype}: {count}")

        spy_client.close()
        rev_client.close()
        store_client.close()
