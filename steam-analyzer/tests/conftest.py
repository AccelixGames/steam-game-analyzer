import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    """Provides a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    """Provides a fresh database connection with schema initialized."""
    from steam_crawler.db.schema import init_db

    conn = init_db(str(db_path))
    from steam_analyzer.error_logger import init_analysis_logs
    init_analysis_logs(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db_conn):
    """Provides a db_conn pre-seeded with sample games, game_tags, and reviews."""
    conn = db_conn

    # Insert tag_catalog entries (needed for FK)
    conn.execute(
        "INSERT INTO tag_catalog (tag_name, total_games) VALUES (?, ?)",
        ("Roguelike", 500),
    )
    conn.execute(
        "INSERT INTO tag_catalog (tag_name, total_games) VALUES (?, ?)",
        ("RPG", 1000),
    )
    conn.execute(
        "INSERT INTO tag_catalog (tag_name, total_games) VALUES (?, ?)",
        ("Action", 2000),
    )

    # Insert sample games
    conn.execute(
        """INSERT INTO games (appid, name, positive, negative, source_tag)
           VALUES (?, ?, ?, ?, ?)""",
        (1, "Game Alpha", 800, 200, "tag:Roguelike"),
    )
    conn.execute(
        """INSERT INTO games (appid, name, positive, negative, source_tag)
           VALUES (?, ?, ?, ?, ?)""",
        (2, "Game Beta", 600, 100, "tag:Roguelike"),
    )
    conn.execute(
        """INSERT INTO games (appid, name, positive, negative, source_tag)
           VALUES (?, ?, ?, ?, ?)""",
        (3, "Game Gamma", 300, 50, "tag:RPG"),
    )

    # Insert game_tags
    conn.execute(
        "INSERT INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
        (1, "Roguelike", 9000),
    )
    conn.execute(
        "INSERT INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
        (1, "Action", 5000),
    )
    conn.execute(
        "INSERT INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
        (2, "Roguelike", 7000),
    )
    conn.execute(
        "INSERT INTO game_tags (appid, tag_name, vote_count) VALUES (?, ?, ?)",
        (3, "RPG", 8000),
    )

    # Insert sample reviews for appid=1
    conn.execute(
        """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("rev1", 1, "english", "Excellent game, highly recommended!", True, 120, 0.9),
    )
    conn.execute(
        """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("rev2", 1, "english", "Not my cup of tea.", False, 10, 0.2),
    )
    conn.execute(
        """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("rev3", 1, "korean", "정말 재미있는 게임입니다.", True, 300, 0.85),
    )
    # Review for appid=2
    conn.execute(
        """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("rev4", 2, "english", "Decent but repetitive.", False, 50, 0.4),
    )
    # Long review (>500 chars) for truncation test
    long_text = "A" * 600
    conn.execute(
        """INSERT INTO reviews
               (recommendation_id, appid, language, review_text, voted_up,
                playtime_forever, weighted_vote_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("rev5", 1, "english", long_text, True, 200, 0.95),
    )

    conn.commit()
    yield conn
