"""Database CRUD operations for steam-crawler."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from steam_crawler.models.game import GameSummary
from steam_crawler.models.review import Review


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_game(
    conn: sqlite3.Connection, game: GameSummary, version: int
) -> tuple[bool, dict[str, tuple[str, str]]]:
    """UPSERT a game record. Returns (is_new, changes_dict).

    changes_dict maps field_name -> (old_value, new_value) as strings.
    """
    existing = conn.execute(
        "SELECT * FROM games WHERE appid = ?", (game.appid,)
    ).fetchone()

    now = _now()

    if existing is None:
        conn.execute(
            """
            INSERT INTO games
                (appid, name, positive, negative, owners, price,
                 avg_playtime, score_rank, source_tag, first_seen_ver, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game.appid, game.name, game.positive, game.negative,
                game.owners, game.price,
                game.avg_playtime, game.score_rank, game.source_tag,
                version, now,
            ),
        )
        conn.commit()
        return True, {}

    # Detect changes in tracked fields
    tracked_fields = ["positive", "negative", "owners", "price", "avg_playtime", "score_rank"]
    changes: dict[str, tuple[str, str]] = {}

    new_values = {
        "positive": game.positive,
        "negative": game.negative,
        "owners": game.owners,
        "price": game.price,
        "avg_playtime": game.avg_playtime,
        "score_rank": game.score_rank,
    }

    for field in tracked_fields:
        old_val = existing[field]
        new_val = new_values[field]
        if new_val is not None and str(old_val) != str(new_val):
            changes[field] = (str(old_val), str(new_val))

    conn.execute(
        """
        UPDATE games SET
            name = ?, positive = ?, negative = ?, owners = ?, price = ?,
            avg_playtime = ?, score_rank = ?, updated_at = ?
        WHERE appid = ?
        """,
        (
            game.name,
            game.positive if game.positive is not None else existing["positive"],
            game.negative if game.negative is not None else existing["negative"],
            game.owners if game.owners is not None else existing["owners"],
            game.price if game.price is not None else existing["price"],
            game.avg_playtime if game.avg_playtime is not None else existing["avg_playtime"],
            game.score_rank if game.score_rank is not None else existing["score_rank"],
            now,
            game.appid,
        ),
    )
    conn.commit()
    return False, changes


def insert_reviews_batch(
    conn: sqlite3.Connection, reviews: list[Review], version: int = 0
) -> int:
    """INSERT OR IGNORE reviews. Returns number actually inserted."""
    now = _now()
    inserted = 0

    for review in reviews:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO reviews
                (recommendation_id, appid, language, review_text, voted_up,
                 playtime_forever, playtime_at_review, early_access, steam_purchase,
                 received_for_free, dev_response, timestamp_created, votes_up,
                 votes_funny, weighted_vote_score, comment_count, author_steamid,
                 author_num_reviews, author_playtime_forever, collected_ver, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.recommendation_id, review.appid, review.language,
                review.review_text, review.voted_up, review.playtime_forever,
                review.playtime_at_review, review.early_access, review.steam_purchase,
                review.received_for_free, review.dev_response, review.timestamp_created,
                review.votes_up, review.votes_funny, review.weighted_vote_score,
                review.comment_count, review.author_steamid, review.author_num_reviews,
                review.author_playtime_forever, version, now,
            ),
        )
        inserted += cursor.rowcount

    conn.commit()
    return inserted


def create_version(
    conn: sqlite3.Connection,
    query_type: str,
    query_value: str | None = None,
    config: str | None = None,
    note: str | None = None,
) -> int:
    """Create a data_versions entry with status='running'. Returns version id."""
    cursor = conn.execute(
        """
        INSERT INTO data_versions (query_type, query_value, status, config, note)
        VALUES (?, ?, 'running', ?, ?)
        """,
        (query_type, query_value, config, note),
    )
    conn.commit()
    return cursor.lastrowid


def update_version_status(
    conn: sqlite3.Connection,
    version: int,
    status: str,
    games_total: int | None = None,
    reviews_total: int | None = None,
) -> None:
    """Update the status and totals of a data_versions entry."""
    conn.execute(
        """
        UPDATE data_versions SET status = ?, games_total = ?, reviews_total = ?
        WHERE version = ?
        """,
        (status, games_total, reviews_total, version),
    )
    conn.commit()


def update_game_review_stats(
    conn: sqlite3.Connection,
    appid: int,
    steam_positive: int | None = None,
    steam_negative: int | None = None,
    review_score: str | None = None,
) -> None:
    """Update Steam review stats on the games table."""
    conn.execute(
        """
        UPDATE games SET steam_positive = ?, steam_negative = ?, review_score = ?,
            updated_at = ?
        WHERE appid = ?
        """,
        (steam_positive, steam_negative, review_score, _now(), appid),
    )
    conn.commit()


def get_games_by_version(
    conn: sqlite3.Connection, source_tag: str | None = None
) -> list[dict]:
    """Return games filtered by source_tag, sorted by positive desc."""
    if source_tag is not None:
        cursor = conn.execute(
            "SELECT * FROM games WHERE source_tag = ? ORDER BY positive DESC",
            (source_tag,),
        )
    else:
        cursor = conn.execute("SELECT * FROM games ORDER BY positive DESC")
    return [dict(row) for row in cursor.fetchall()]


def upsert_genre_catalog(conn: sqlite3.Connection, genre_name: str, total_games: int) -> None:
    """Insert or update a genre in the catalog."""
    conn.execute(
        "INSERT OR REPLACE INTO genre_catalog (genre_name, total_games, fetched_at) VALUES (?, ?, ?)",
        (genre_name, total_games, _now()),
    )
    conn.commit()


def get_genre_catalog(conn: sqlite3.Connection) -> list[dict]:
    """Get genre catalog with collection coverage."""
    rows = conn.execute("""
        SELECT gc.genre_name, gc.total_games, gc.fetched_at,
               count(gg.appid) as collected_games
        FROM genre_catalog gc
        LEFT JOIN game_genres gg ON gc.genre_name = gg.genre_name
        GROUP BY gc.genre_name
        ORDER BY gc.total_games DESC
    """).fetchall()
    return [dict(r) for r in rows]


def upsert_game_genres(conn: sqlite3.Connection, appid: int, genres: list[str]) -> int:
    """Insert or replace game genres into game_genres table.
    Auto-creates genre_catalog entries if they don't exist.
    Returns count inserted.
    """
    inserted = 0
    for genre_name in genres:
        # Ensure genre exists in catalog (FK constraint)
        conn.execute(
            "INSERT OR IGNORE INTO genre_catalog (genre_name) VALUES (?)",
            (genre_name,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_genres (appid, genre_name) VALUES (?, ?)",
            (appid, genre_name),
        )
        inserted += 1
    conn.commit()
    return inserted


def upsert_tag_catalog(conn: sqlite3.Connection, tag_name: str, total_games: int | None = None) -> None:
    """Insert or update a tag in the catalog."""
    if total_games is not None:
        conn.execute(
            "INSERT OR REPLACE INTO tag_catalog (tag_name, total_games, fetched_at) VALUES (?, ?, ?)",
            (tag_name, total_games, _now()),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO tag_catalog (tag_name) VALUES (?)",
            (tag_name,),
        )
    conn.commit()


def get_tag_catalog(conn: sqlite3.Connection) -> list[dict]:
    """Get tag catalog with collection coverage."""
    rows = conn.execute("""
        SELECT tc.tag_name, tc.total_games, tc.fetched_at,
               count(gt.appid) as collected_games,
               sum(gt.vote_count) as total_votes
        FROM tag_catalog tc
        LEFT JOIN game_tags gt ON tc.tag_name = gt.tag_name
        GROUP BY tc.tag_name
        ORDER BY collected_games DESC, total_votes DESC
    """).fetchall()
    return [dict(r) for r in rows]


def upsert_game_tags(conn: sqlite3.Connection, appid: int, tags: dict[str, int]) -> int:
    """Insert or replace game tags into game_tags table.
    Auto-creates tag_catalog entries if they don't exist.
    Returns count inserted.
    """
    inserted = 0
    for tag_name, vote_count in tags.items():
        conn.execute(
            "INSERT OR IGNORE INTO tag_catalog (tag_name) VALUES (?)",
            (tag_name,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
            (appid, tag_name, vote_count),
        )
        inserted += 1
    conn.commit()
    return inserted


def update_game_store_details(
    conn: sqlite3.Connection,
    appid: int,
    short_description_en: str | None = None,
    short_description_ko: str | None = None,
    header_image: str | None = None,
) -> None:
    """Update store page details on the games table."""
    conn.execute(
        "UPDATE games SET short_description_en=?, short_description_ko=?, header_image=?, updated_at=? WHERE appid=?",
        (short_description_en, short_description_ko, header_image, _now(), appid),
    )
    conn.commit()


def upsert_game_media(
    conn: sqlite3.Connection,
    appid: int,
    media_type: str,
    media_id: int,
    name: str | None = None,
    url_thumbnail: str | None = None,
    url_full: str | None = None,
) -> None:
    """Insert or replace a media item (screenshot or movie)."""
    conn.execute(
        """INSERT OR REPLACE INTO game_media
        (appid, media_type, media_id, name, url_thumbnail, url_full)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (appid, media_type, media_id, name, url_thumbnail, url_full),
    )
    conn.commit()


def update_game_igdb_details(
    conn: sqlite3.Connection,
    appid: int,
    igdb_id: int,
    igdb_summary: str | None = None,
    igdb_storyline: str | None = None,
    igdb_rating: float | None = None,
) -> None:
    """Update IGDB enrichment data on the games table."""
    conn.execute(
        "UPDATE games SET igdb_id=?, igdb_summary=?, igdb_storyline=?, igdb_rating=?, updated_at=? WHERE appid=?",
        (igdb_id, igdb_summary, igdb_storyline, igdb_rating, _now(), appid),
    )
    conn.commit()


def update_game_rawg_details(
    conn: sqlite3.Connection,
    appid: int,
    rawg_id: int,
    rawg_description: str | None = None,
    rawg_rating: float | None = None,
    metacritic_score: int | None = None,
) -> None:
    """Update RAWG enrichment data on the games table."""
    conn.execute(
        "UPDATE games SET rawg_id=?, rawg_description=?, rawg_rating=?, metacritic_score=?, updated_at=? WHERE appid=?",
        (rawg_id, rawg_description, rawg_rating, metacritic_score, _now(), appid),
    )
    conn.commit()


def upsert_game_themes(conn: sqlite3.Connection, appid: int, themes: dict[int, str]) -> int:
    """Insert or replace game themes. themes = {igdb_theme_id: theme_name}.
    Auto-creates theme_catalog entries. Returns count inserted."""
    inserted = 0
    for theme_id, theme_name in themes.items():
        conn.execute(
            "INSERT OR REPLACE INTO theme_catalog (id, name) VALUES (?, ?)",
            (theme_id, theme_name),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_themes (appid, theme_id, source) VALUES (?, ?, 'igdb')",
            (appid, theme_id),
        )
        inserted += 1
    conn.commit()
    return inserted


def upsert_game_keywords(conn: sqlite3.Connection, appid: int, keywords: dict[int, str]) -> int:
    """Insert or replace game keywords. keywords = {igdb_keyword_id: keyword_name}.
    Auto-creates keyword_catalog entries. Returns count inserted."""
    inserted = 0
    for keyword_id, keyword_name in keywords.items():
        conn.execute(
            "INSERT OR REPLACE INTO keyword_catalog (id, name) VALUES (?, ?)",
            (keyword_id, keyword_name),
        )
        conn.execute(
            "INSERT OR REPLACE INTO game_keywords (appid, keyword_id, source) VALUES (?, ?, 'igdb')",
            (appid, keyword_id),
        )
        inserted += 1
    conn.commit()
    return inserted


def get_games_needing_enrichment(
    conn: sqlite3.Connection, source: str, source_tag: str | None = None,
) -> list[dict]:
    """Return games that haven't been enriched by the given source.
    source: 'igdb' or 'rawg'. Excludes id=-1 (unmatchable)."""
    id_col = "igdb_id" if source == "igdb" else "rawg_id"
    if source_tag:
        rows = conn.execute(
            f"SELECT appid, name FROM games WHERE ({id_col} IS NULL) AND source_tag = ? ORDER BY positive DESC",
            (source_tag,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT appid, name FROM games WHERE ({id_col} IS NULL) ORDER BY positive DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_collection_status(
    conn: sqlite3.Connection, appid: int, version: int, **kwargs: Any
) -> None:
    """Upsert game_collection_status for (appid, version)."""
    now = _now()

    existing = conn.execute(
        "SELECT * FROM game_collection_status WHERE appid = ? AND version = ?",
        (appid, version),
    ).fetchone()

    if existing is None:
        fields = ["appid", "version", "updated_at"] + list(kwargs.keys())
        values = [appid, version, now] + list(kwargs.values())
        placeholders = ", ".join("?" * len(values))
        col_names = ", ".join(fields)
        conn.execute(
            f"INSERT INTO game_collection_status ({col_names}) VALUES ({placeholders})",
            values,
        )
    else:
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [now, appid, version]
        conn.execute(
            f"UPDATE game_collection_status SET {set_clause}, updated_at = ? WHERE appid = ? AND version = ?",
            values,
        )

    conn.commit()
