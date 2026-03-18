"""CLI entry point for steam-crawler."""
from __future__ import annotations
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from steam_crawler.db.schema import init_db

console = Console()
DEFAULT_DB = str(Path.cwd().parent / "data" / "steam.db")


@click.group()
def main():
    """Steam game data crawler."""
    pass


@main.command()
@click.option("--tag", default=None, help='Tag filter (e.g., "Roguelike")')
@click.option("--genre", default=None, help='Genre filter (e.g., "Simulation")')
@click.option("--top100", is_flag=True, help="Top 100 in last 2 weeks")
@click.option("--limit", default=50, help="Max games to collect in Step 1")
@click.option("--top-n", default=10, help="Top N games for review crawling")
@click.option("--max-reviews", default=500, help="Max reviews per game")
@click.option("--language", default="all", help="Review language filter")
@click.option("--review-type", default="all", type=click.Choice(["all", "positive", "negative"]))
@click.option("--resume", is_flag=True, help="Resume interrupted collection")
@click.option("--step", default=None, type=click.IntRange(1, 3), help="Run specific step only")
@click.option("--note", default=None, help="Note for this version")
@click.option("--db", default=DEFAULT_DB, help="Database path")
def collect(tag, genre, top100, limit, top_n, max_reviews, language, review_type, resume, step, note, db):
    """Collect game data and reviews from Steam."""
    if not any([tag, genre, top100]):
        raise click.UsageError("Specify one of: --tag, --genre, --top100")
    if sum(bool(x) for x in [tag, genre, top100]) > 1:
        raise click.UsageError("Specify only one of: --tag, --genre, --top100")

    conn = init_db(db)
    query_type = "tag" if tag else ("genre" if genre else "top100")
    query_value = tag or genre

    from steam_crawler.pipeline.runner import run_pipeline
    try:
        run_pipeline(
            conn, query_type=query_type, query_value=query_value,
            limit=limit, top_n=top_n, max_reviews=max_reviews,
            language=language, review_type=review_type,
            step=step, resume=resume, note=note,
        )
    finally:
        conn.close()


@main.command()
@click.option("--db", default=DEFAULT_DB, help="Database path")
def versions(db):
    """List collection versions."""
    conn = init_db(db)
    rows = conn.execute("SELECT * FROM data_versions ORDER BY version DESC").fetchall()
    if not rows:
        console.print("No versions found.")
        conn.close()
        return
    table = Table(title="Collection Versions")
    table.add_column("Ver", style="bold")
    table.add_column("Type")
    table.add_column("Value")
    table.add_column("Status")
    table.add_column("Games")
    table.add_column("Reviews")
    table.add_column("Created")
    table.add_column("Note")
    for r in rows:
        table.add_row(
            str(r["version"]), r["query_type"], r["query_value"] or "",
            r["status"], str(r["games_total"] or ""), str(r["reviews_total"] or ""),
            r["created_at"] or "", r["note"] or "",
        )
    console.print(table)
    conn.close()


@main.command()
@click.argument("v1", type=int)
@click.argument("v2", type=int)
@click.option("--db", default=DEFAULT_DB, help="Database path")
def diff(v1, v2, db):
    """Show changes between two versions."""
    from steam_crawler.db.changelog import get_version_summary
    conn = init_db(db)
    for ver in [v1, v2]:
        summary = get_version_summary(conn, ver)
        console.print(f"\n[bold]Version {ver}:[/bold]")
        if not summary:
            console.print("  No changes recorded.")
        for change_type, count in summary.items():
            console.print(f"  {change_type}: {count}")
    conn.close()


@main.command()
@click.option("--db", default=DEFAULT_DB, help="Database path")
def status(db):
    """Show current collection status."""
    conn = init_db(db)
    latest = conn.execute("SELECT * FROM data_versions ORDER BY version DESC LIMIT 1").fetchone()
    if not latest:
        console.print("No collection data found.")
        conn.close()
        return
    console.print(f"[bold]Latest version: {latest['version']}[/bold] ({latest['status']})")
    console.print(f"  Type: {latest['query_type']}:{latest['query_value'] or ''}")
    total_games = conn.execute("SELECT count(*) FROM games").fetchone()[0]
    total_reviews = conn.execute("SELECT count(*) FROM reviews").fetchone()[0]
    console.print(f"  Games: {total_games}, Reviews: {total_reviews}")
    from steam_crawler.api.resilience import FailureTracker
    tracker = FailureTracker()
    unresolved = tracker.get_unresolved(conn)
    if unresolved:
        console.print(f"  [yellow]Unresolved failures: {len(unresolved)}[/yellow]")
    conn.close()


@main.command()
def genres():
    """Fetch and display all Steam genres with game counts from SteamSpy."""
    from steam_crawler.api.steamspy import SteamSpyClient, STEAM_GENRES

    console.print("[bold]Fetching genre data from SteamSpy...[/bold]")
    client = SteamSpyClient()

    table = Table(title="Steam Genres")
    table.add_column("#", style="dim")
    table.add_column("Genre", style="bold")
    table.add_column("Games", justify="right")

    results = []
    for genre in STEAM_GENRES:
        try:
            count = client.fetch_genre_count(genre)
            results.append((genre, count))
            console.print(f"  {genre}: {count:,}")
        except Exception as e:
            results.append((genre, -1))
            console.print(f"  [red]{genre}: error ({e})[/red]")

    client.close()

    results.sort(key=lambda x: x[1], reverse=True)
    for i, (genre, count) in enumerate(results, 1):
        count_str = f"{count:,}" if count >= 0 else "error"
        table.add_row(str(i), genre, count_str)

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {sum(c for _, c in results if c > 0):,} game-genre entries[/dim]")


if __name__ == "__main__":
    main()
