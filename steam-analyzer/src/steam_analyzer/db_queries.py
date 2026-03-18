"""DB query functions for steam-analyzer.

All functions accept a sqlite3.Connection (with row_factory=sqlite3.Row)
and return list[dict].
"""

from __future__ import annotations

import sqlite3
from typing import Optional

_REVIEW_TEXT_MAX = 500


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def _placeholders(n: int) -> str:
    """Return a SQL placeholder string for n values, e.g. '(?,?,?)'."""
    return "(" + ",".join("?" * n) + ")"


def get_games_by_tag(conn: sqlite3.Connection, tag: str) -> list[dict]:
    """Return all games that have the given tag.

    Queries the indexed ``game_tags`` table and JOINs ``games`` to return
    full game information.
    """
    sql = """
        SELECT g.*
        FROM games g
        JOIN game_tags gt ON g.appid = gt.appid
        WHERE gt.tag_name = ?
        ORDER BY g.appid
    """
    rows = conn.execute(sql, (tag,)).fetchall()
    return _rows_to_dicts(rows)


def get_reviews_for_games(
    conn: sqlite3.Connection,
    appids: list[int],
    language: Optional[str] = None,
) -> list[dict]:
    """Return reviews for the given appids, including the game name.

    JOINs ``games`` so that each row includes ``game_name``.
    Optionally filters by language.
    """
    if not appids:
        return []

    ph = _placeholders(len(appids))
    params: list = list(appids)

    lang_clause = ""
    if language is not None:
        lang_clause = "AND r.language = ?"
        params.append(language)

    sql = f"""
        SELECT r.*, g.name AS game_name
        FROM reviews r
        JOIN games g ON r.appid = g.appid
        WHERE r.appid IN {ph}
        {lang_clause}
        ORDER BY r.recommendation_id
    """
    rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def get_review_samples(
    conn: sqlite3.Connection,
    appids: list[int],
    voted_up: bool,
    limit: int,
    language: Optional[str] = None,
) -> list[dict]:
    """Return a sample of reviews ordered by weighted_vote_score DESC.

    * Filters by ``voted_up`` value.
    * Optionally filters by ``language``.
    * ``review_text`` is truncated to 500 characters.
    * Respects ``limit``.
    """
    if not appids:
        return []

    ph = _placeholders(len(appids))
    params: list = list(appids)
    params.append(int(voted_up))

    lang_clause = ""
    if language is not None:
        lang_clause = "AND r.language = ?"
        params.append(language)

    params.append(limit)

    sql = f"""
        SELECT
            r.recommendation_id,
            r.appid,
            r.language,
            SUBSTR(r.review_text, 1, {_REVIEW_TEXT_MAX}) AS review_text,
            r.voted_up,
            r.playtime_forever,
            r.playtime_at_review,
            r.weighted_vote_score,
            r.votes_up,
            r.votes_funny,
            r.timestamp_created,
            r.author_steamid
        FROM reviews r
        WHERE r.appid IN {ph}
          AND r.voted_up = ?
          {lang_clause}
        ORDER BY r.weighted_vote_score DESC
        LIMIT ?
    """
    rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def get_available_tags(conn: sqlite3.Connection) -> list[dict]:
    """Return all distinct tags that appear in ``game_tags``, with game counts.

    Each result dict contains ``tag_name`` and ``game_count``.
    """
    sql = """
        SELECT tag_name, COUNT(DISTINCT appid) AS game_count
        FROM game_tags
        GROUP BY tag_name
        ORDER BY game_count DESC, tag_name
    """
    rows = conn.execute(sql).fetchall()
    return _rows_to_dicts(rows)
