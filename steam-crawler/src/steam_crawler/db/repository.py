"""Database CRUD operations for steam-crawler."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
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
            INSERT INTO reviews
                (recommendation_id, appid, language, review_text, voted_up,
                 playtime_forever, playtime_at_review, early_access, steam_purchase,
                 received_for_free, dev_response, timestamp_created, votes_up,
                 votes_funny, weighted_vote_score, comment_count, author_steamid,
                 author_num_reviews, author_playtime_forever, collected_ver, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recommendation_id) DO UPDATE SET
                votes_up = excluded.votes_up,
                votes_funny = excluded.votes_funny,
                weighted_vote_score = excluded.weighted_vote_score,
                comment_count = excluded.comment_count,
                collected_at = excluded.collected_at
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
    conn: sqlite3.Connection,
    source_tag: str | None = None,
    lock_owner: str | None = None,
) -> list[dict]:
    """Return games filtered by source_tag, sorted by positive desc.

    If lock_owner is provided, excludes games locked by a different owner
    (non-expired locks only).
    """
    now = datetime.now(timezone.utc).isoformat()

    if lock_owner is not None:
        if source_tag is not None:
            cursor = conn.execute(
                """SELECT g.* FROM games g
                   LEFT JOIN crawl_locks cl
                     ON g.appid = cl.appid AND cl.expires_at >= ? AND cl.owner != ?
                   WHERE g.source_tag = ? AND cl.appid IS NULL
                   ORDER BY g.positive DESC""",
                (now, lock_owner, source_tag),
            )
        else:
            cursor = conn.execute(
                """SELECT g.* FROM games g
                   LEFT JOIN crawl_locks cl
                     ON g.appid = cl.appid AND cl.expires_at >= ? AND cl.owner != ?
                   WHERE cl.appid IS NULL
                   ORDER BY g.positive DESC""",
                (now, lock_owner),
            )
    else:
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
    detailed_description_en: str | None = None,
    detailed_description_ko: str | None = None,
    header_image: str | None = None,
    name_ko: str | None = None,
) -> None:
    """Update store page details on the games table."""
    conn.execute(
        "UPDATE games SET name_ko=?, short_description_en=?, short_description_ko=?, detailed_description_en=?, detailed_description_ko=?, header_image=?, updated_at=? WHERE appid=?",
        (name_ko, short_description_en, short_description_ko, detailed_description_en, detailed_description_ko, header_image, _now(), appid),
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
    rawg_ratings_count: int | None = None,
    rawg_added: int | None = None,
    rawg_status_yet: int | None = None,
    rawg_status_owned: int | None = None,
    rawg_status_beaten: int | None = None,
    rawg_status_toplay: int | None = None,
    rawg_status_dropped: int | None = None,
    rawg_status_playing: int | None = None,
    rawg_exceptional_pct: float | None = None,
    rawg_recommended_pct: float | None = None,
    rawg_meh_pct: float | None = None,
    rawg_skip_pct: float | None = None,
) -> None:
    """Update RAWG enrichment data on the games table."""
    conn.execute(
        """UPDATE games SET rawg_id=?, rawg_description=?, rawg_rating=?,
           metacritic_score=?, rawg_ratings_count=?, rawg_added=?,
           rawg_status_yet=?, rawg_status_owned=?, rawg_status_beaten=?,
           rawg_status_toplay=?, rawg_status_dropped=?, rawg_status_playing=?,
           rawg_exceptional_pct=?, rawg_recommended_pct=?,
           rawg_meh_pct=?, rawg_skip_pct=?,
           updated_at=? WHERE appid=?""",
        (rawg_id, rawg_description, rawg_rating, metacritic_score,
         rawg_ratings_count, rawg_added,
         rawg_status_yet, rawg_status_owned, rawg_status_beaten,
         rawg_status_toplay, rawg_status_dropped, rawg_status_playing,
         rawg_exceptional_pct, rawg_recommended_pct,
         rawg_meh_pct, rawg_skip_pct,
         _now(), appid),
    )
    conn.commit()


def update_game_twitch_stats(
    conn: sqlite3.Connection,
    appid: int,
    twitch_game_id: str,
    stream_count: int,
    viewer_count: int,
    top_language: str | None = None,
    lang_distribution: str | None = None,
) -> None:
    """Update Twitch streaming stats on the games table."""
    conn.execute(
        """UPDATE games SET twitch_game_id=?, twitch_stream_count=?,
           twitch_viewer_count=?, twitch_top_language=?,
           twitch_lang_distribution=?, twitch_fetched_at=?,
           updated_at=? WHERE appid=?""",
        (twitch_game_id, stream_count, viewer_count,
         top_language, lang_distribution, _now(), _now(), appid),
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


def validate_source_tags(
    conn: sqlite3.Connection,
    source_tag: str | None = None,
) -> list[dict]:
    """Validate that games' source_tag matches their actual tags in game_tags/game_genres.

    For source_tag like "tag:X", checks game_tags for tag_name = X.
    For source_tag like "genre:X", checks game_genres for genre_name = X.
    Games that fail validation get source_tag set to "unverified:<original>".

    Returns list of mismatched games [{appid, name, source_tag}].
    """
    if source_tag is None:
        return []

    # Parse source_tag prefix and value
    if ":" not in source_tag:
        return []
    prefix, _, tag_value = source_tag.partition(":")
    if not tag_value:
        return []

    # Pick the right join table
    if prefix == "tag":
        check_sql = """
            SELECT g.appid, g.name, g.source_tag
            FROM games g
            WHERE g.source_tag = ?
              AND g.appid NOT IN (
                  SELECT gt.appid FROM game_tags gt WHERE gt.tag_name = ?
              )
              AND g.appid IN (
                  SELECT gt2.appid FROM game_tags gt2
              )
        """
    elif prefix == "genre":
        check_sql = """
            SELECT g.appid, g.name, g.source_tag
            FROM games g
            WHERE g.source_tag = ?
              AND g.appid NOT IN (
                  SELECT gg.appid FROM game_genres gg WHERE gg.genre_name = ?
              )
              AND g.appid IN (
                  SELECT gg2.appid FROM game_genres gg2
              )
        """
    else:
        return []

    rows = conn.execute(check_sql, (source_tag, tag_value)).fetchall()
    mismatched = [dict(r) for r in rows]

    if mismatched:
        now = _now()
        for game in mismatched:
            conn.execute(
                "UPDATE games SET source_tag = ?, updated_at = ? WHERE appid = ?",
                (f"unverified:{source_tag}", now, game["appid"]),
            )
        conn.commit()

    return mismatched


def get_games_needing_enrichment(
    conn: sqlite3.Connection,
    source: str,
    source_tag: str | None = None,
    lock_owner: str | None = None,
) -> list[dict]:
    """Return games that haven't been enriched by the given source.
    source: 'igdb' or 'rawg'. Excludes id=-1 (unmatchable).
    If lock_owner is provided, excludes games locked by a different owner.
    """
    id_col_map = {
        "igdb": "igdb_id",
        "rawg": "rawg_id",
        "twitch": "twitch_game_id",
        "hltb": "hltb_id",
        "cheapshark": "cheapshark_deal_rating",
        "opencritic": "opencritic_id",
        "pcgamingwiki": "pcgw_engine",
        "wikidata": "wikidata_id",
    }
    id_col = id_col_map[source]
    now = datetime.now(timezone.utc).isoformat()

    if lock_owner is not None:
        if source_tag:
            rows = conn.execute(
                f"""SELECT g.appid, g.name FROM games g
                    LEFT JOIN crawl_locks cl
                      ON g.appid = cl.appid AND cl.expires_at >= ? AND cl.owner != ?
                    WHERE g.{id_col} IS NULL AND g.source_tag = ? AND cl.appid IS NULL
                    ORDER BY g.positive DESC""",
                (now, lock_owner, source_tag),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT g.appid, g.name FROM games g
                    LEFT JOIN crawl_locks cl
                      ON g.appid = cl.appid AND cl.expires_at >= ? AND cl.owner != ?
                    WHERE g.{id_col} IS NULL AND cl.appid IS NULL
                    ORDER BY g.positive DESC""",
                (now, lock_owner),
            ).fetchall()
    else:
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



def update_game_hltb(
    conn: sqlite3.Connection,
    appid: int,
    hltb_id: int,
    main_story: float | None = None,
    main_extra: float | None = None,
    completionist: float | None = None,
) -> None:
    """Update HowLongToBeat completion times."""
    conn.execute(
        """UPDATE games SET hltb_id=?, hltb_main_story=?,
           hltb_main_extra=?, hltb_completionist=?,
           updated_at=? WHERE appid=?""",
        (hltb_id, main_story, main_extra, completionist, _now(), appid),
    )
    conn.commit()


def update_game_cheapshark(
    conn: sqlite3.Connection,
    appid: int,
    deal_rating: float | None = None,
    lowest_price: float | None = None,
    lowest_price_date: str | None = None,
) -> None:
    """Update CheapShark deal/price data."""
    conn.execute(
        """UPDATE games SET cheapshark_deal_rating=?,
           cheapshark_lowest_price=?, cheapshark_lowest_price_date=?,
           updated_at=? WHERE appid=?""",
        (deal_rating, lowest_price, lowest_price_date, _now(), appid),
    )
    conn.commit()


def update_game_opencritic(
    conn: sqlite3.Connection,
    appid: int,
    opencritic_id: int,
    score: float | None = None,
    pct_recommend: float | None = None,
    tier: str | None = None,
    review_count: int | None = None,
) -> None:
    """Update OpenCritic aggregate scores."""
    conn.execute(
        """UPDATE games SET opencritic_id=?, opencritic_score=?,
           opencritic_pct_recommend=?, opencritic_tier=?,
           opencritic_review_count=?,
           updated_at=? WHERE appid=?""",
        (opencritic_id, score, pct_recommend, tier, review_count, _now(), appid),
    )
    conn.commit()


def update_game_pcgamingwiki(
    conn: sqlite3.Connection,
    appid: int,
    engine: str | None = None,
    has_ultrawide: bool | None = None,
    has_hdr: bool | None = None,
    has_controller: bool | None = None,
    graphics_api: str | None = None,
) -> None:
    """Update PCGamingWiki technical data."""
    conn.execute(
        """UPDATE games SET pcgw_engine=?, pcgw_has_ultrawide=?,
           pcgw_has_hdr=?, pcgw_has_controller=?, pcgw_graphics_api=?,
           updated_at=? WHERE appid=?""",
        (engine, int(has_ultrawide) if has_ultrawide is not None else None,
         int(has_hdr) if has_hdr is not None else None,
         int(has_controller) if has_controller is not None else None,
         graphics_api, _now(), appid),
    )
    conn.commit()


def upsert_external_review(
    conn: sqlite3.Connection,
    appid: int,
    source: str,
    source_id: str,
    title: str | None = None,
    score: float | None = None,
    author: str | None = None,
    outlet: str | None = None,
    url: str | None = None,
    snippet: str | None = None,
    view_count: int | None = None,
    like_ratio: float | None = None,
    published_at: str | None = None,
) -> None:
    """Insert or update an external review."""
    conn.execute(
        """INSERT INTO external_reviews
           (appid, source, source_id, title, score, author, outlet, url,
            snippet, view_count, like_ratio, published_at, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(appid, source, source_id) DO UPDATE SET
               title=excluded.title, score=excluded.score,
               snippet=excluded.snippet, view_count=excluded.view_count,
               like_ratio=excluded.like_ratio, fetched_at=excluded.fetched_at""",
        (appid, source, source_id, title, score, author, outlet, url,
         snippet, view_count, like_ratio, published_at, _now()),
    )
    conn.commit()


def get_external_reviews(
    conn: sqlite3.Connection,
    appid: int,
    source: str | None = None,
) -> list[dict]:
    """Get external reviews for a game, optionally filtered by source."""
    if source:
        rows = conn.execute(
            "SELECT * FROM external_reviews WHERE appid=? AND source=? ORDER BY score DESC",
            (appid, source),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM external_reviews WHERE appid=? ORDER BY source, score DESC",
            (appid,),
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_wikidata_claims(
    conn: sqlite3.Connection,
    appid: int,
    claims: list[dict],
) -> int:
    """Insert or update Wikidata claims for a game.
    Each claim dict: {claim_type, name, wikidata_id, property_id, extra?}
    Returns count inserted/updated.
    """
    now = _now()
    count = 0
    for claim in claims:
        conn.execute(
            """INSERT INTO game_wikidata_claims
               (appid, claim_type, name, wikidata_id, property_id, extra, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(appid, claim_type, wikidata_id) DO UPDATE SET
                   name=excluded.name, extra=excluded.extra, fetched_at=excluded.fetched_at""",
            (appid, claim["claim_type"], claim["name"],
             claim.get("wikidata_id"), claim.get("property_id"),
             claim.get("extra"), now),
        )
        count += 1
    conn.commit()
    return count


def get_wikidata_claims(
    conn: sqlite3.Connection,
    appid: int,
    claim_type: str | None = None,
) -> list[dict]:
    """Get Wikidata claims for a game, optionally filtered by type."""
    if claim_type:
        rows = conn.execute(
            "SELECT * FROM game_wikidata_claims WHERE appid=? AND claim_type=? ORDER BY name",
            (appid, claim_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM game_wikidata_claims WHERE appid=? ORDER BY claim_type, name",
            (appid,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_game_wikidata(
    conn: sqlite3.Connection,
    appid: int,
    wikidata_id: str,
) -> None:
    """Update Wikidata Q-ID and fetch timestamp on games table."""
    conn.execute(
        "UPDATE games SET wikidata_id=?, wikidata_fetched_at=?, updated_at=? WHERE appid=?",
        (wikidata_id, _now(), _now(), appid),
    )
    conn.commit()


# --------------- Crawl Locks ---------------

LOCK_TTL_SECONDS = 300  # 5 minutes


def acquire_crawl_lock(
    conn: sqlite3.Connection, appid: int, owner: str = "",
) -> bool:
    """Try to acquire a crawl lock for the given appid.

    Atomically inserts a lock row. Returns True if acquired, False if
    another active (non-expired) lock exists.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=LOCK_TTL_SECONDS)

    # Clean up expired locks for this appid first
    conn.execute(
        "DELETE FROM crawl_locks WHERE appid = ? AND expires_at < ?",
        (appid, now.isoformat()),
    )

    # Atomic acquire: INSERT OR IGNORE ensures only one winner
    cursor = conn.execute(
        "INSERT OR IGNORE INTO crawl_locks (appid, locked_at, expires_at, owner) VALUES (?, ?, ?, ?)",
        (appid, now.isoformat(), expires.isoformat(), owner),
    )
    conn.commit()
    return cursor.rowcount == 1


def release_crawl_lock(conn: sqlite3.Connection, appid: int) -> None:
    """Release a crawl lock for the given appid."""
    conn.execute("DELETE FROM crawl_locks WHERE appid = ?", (appid,))
    conn.commit()


def cleanup_expired_locks(conn: sqlite3.Connection) -> int:
    """Remove all expired locks. Returns count removed."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "DELETE FROM crawl_locks WHERE expires_at < ?", (now,)
    )
    conn.commit()
    return cursor.rowcount


def get_active_locks(conn: sqlite3.Connection) -> list[dict]:
    """Return all currently active (non-expired) locks."""
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        "SELECT appid, locked_at, expires_at, owner FROM crawl_locks WHERE expires_at >= ?",
        (now,),
    ).fetchall()
    return [dict(r) for r in rows]
