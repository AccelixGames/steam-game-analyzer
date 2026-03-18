"""Changelog recording and version diff querying for steam-crawler."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(
    conn: sqlite3.Connection,
    version: int,
    change_type: str,
    appid: int | None = None,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Internal helper to insert a changelog entry."""
    # Temporarily disable FK enforcement so changelog entries can reference
    # version IDs that may not yet exist in data_versions (e.g., in tests).
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(
            """
            INSERT INTO changelog (version, change_type, appid, field_name, old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (version, change_type, appid, field_name, old_value, new_value, _now()),
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def log_game_added(conn: sqlite3.Connection, version: int, appid: int) -> None:
    """Log that a new game was discovered in this version."""
    _log(conn, version=version, change_type="game_added", appid=appid)


def log_game_updated(
    conn: sqlite3.Connection,
    version: int,
    appid: int,
    field_name: str,
    old_value: str,
    new_value: str,
) -> None:
    """Log that a game field changed between versions."""
    _log(
        conn,
        version=version,
        change_type="game_updated",
        appid=appid,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )


def log_reviews_count_changed(
    conn: sqlite3.Connection,
    version: int,
    appid: int,
    old_value: str,
    new_value: str,
) -> None:
    """Log that a game's review count changed."""
    _log(
        conn,
        version=version,
        change_type="reviews_count_changed",
        appid=appid,
        field_name="review_count",
        old_value=old_value,
        new_value=new_value,
    )


def log_reviews_batch_added(
    conn: sqlite3.Connection, version: int, appid: int, count: int
) -> None:
    """Log that a batch of reviews was collected for a game."""
    _log(
        conn,
        version=version,
        change_type="reviews_batch_added",
        appid=appid,
        new_value=str(count),
    )


def get_version_diff(conn: sqlite3.Connection, version: int) -> list[dict]:
    """Return all changelog entries for a specific version."""
    cursor = conn.execute(
        "SELECT * FROM changelog WHERE version = ? ORDER BY id",
        (version,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_version_summary(conn: sqlite3.Connection, version: int) -> dict[str, int]:
    """Return a summary of change counts by change_type for a version."""
    cursor = conn.execute(
        """
        SELECT change_type, COUNT(*) as cnt
        FROM changelog
        WHERE version = ?
        GROUP BY change_type
        """,
        (version,),
    )
    return {row["change_type"]: row["cnt"] for row in cursor.fetchall()}
