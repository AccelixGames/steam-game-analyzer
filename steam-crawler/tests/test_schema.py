def test_init_db_creates_all_tables(db_conn):
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "games",
        "reviews",
        "data_versions",
        "changelog",
        "rate_limit_stats",
        "failure_logs",
        "tag_catalog",
        "game_tags",
        "genre_catalog",
        "game_genres",
        "game_media",
        "game_collection_status",
    }
    assert expected.issubset(tables)


def test_init_db_creates_indexes(db_conn):
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    assert "idx_reviews_appid" in indexes
    assert "idx_changelog_version" in indexes
    assert "idx_failure_logs_type" in indexes
    assert "idx_game_tags_tag" in indexes
    assert "idx_game_genres_genre" in indexes


def test_init_db_is_idempotent(db_path):
    from steam_crawler.db.schema import init_db

    conn1 = init_db(str(db_path))
    conn1.close()
    conn2 = init_db(str(db_path))
    tables = conn2.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    conn2.close()
    assert tables >= 12


def test_games_has_igdb_columns(db_conn):
    """games table has IGDB enrichment columns."""
    row = db_conn.execute("PRAGMA table_info(games)").fetchall()
    col_names = [r["name"] for r in row]
    assert "igdb_id" in col_names
    assert "igdb_summary" in col_names
    assert "igdb_storyline" in col_names
    assert "igdb_rating" in col_names


def test_games_has_rawg_columns(db_conn):
    """games table has RAWG enrichment columns."""
    row = db_conn.execute("PRAGMA table_info(games)").fetchall()
    col_names = [r["name"] for r in row]
    assert "rawg_id" in col_names
    assert "rawg_description" in col_names
    assert "rawg_rating" in col_names
    assert "metacritic_score" in col_names


def test_theme_catalog_table_exists(db_conn):
    """theme_catalog and game_themes tables exist with correct schema."""
    db_conn.execute("INSERT INTO theme_catalog (id, name) VALUES (1, 'Horror')")
    db_conn.execute("INSERT INTO games (appid, name) VALUES (730, 'CS2')")
    db_conn.execute(
        "INSERT INTO game_themes (appid, theme_id, source) VALUES (730, 1, 'igdb')"
    )
    db_conn.commit()
    row = db_conn.execute("SELECT * FROM game_themes WHERE appid=730").fetchone()
    assert row["theme_id"] == 1
    assert row["source"] == "igdb"


def test_keyword_catalog_table_exists(db_conn):
    """keyword_catalog and game_keywords tables exist with correct schema."""
    db_conn.execute("INSERT INTO keyword_catalog (id, name) VALUES (1, 'roguelike')")
    db_conn.execute("INSERT INTO games (appid, name) VALUES (730, 'CS2')")
    db_conn.execute(
        "INSERT INTO game_keywords (appid, keyword_id, source) VALUES (730, 1, 'igdb')"
    )
    db_conn.commit()
    row = db_conn.execute("SELECT * FROM game_keywords WHERE appid=730").fetchone()
    assert row["keyword_id"] == 1


def test_valid_reviews_view_exists(db_conn):
    """valid_reviews View is created by init_db."""
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    )
    views = {row["name"] for row in cursor.fetchall()}
    assert "valid_reviews" in views


def _insert_review(conn, recommendation_id, appid, review_text,
                   playtime_at_review=100, voted_up=1,
                   weighted_vote_score=0.5, votes_up=1):
    """테스트용 리뷰 삽입 헬퍼."""
    conn.execute("INSERT OR IGNORE INTO games (appid, name) VALUES (?, ?)",
                 (appid, f"Game{appid}"))
    conn.execute(
        """INSERT INTO reviews
           (recommendation_id, appid, review_text, playtime_at_review,
            voted_up, weighted_vote_score, votes_up)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (recommendation_id, appid, review_text, playtime_at_review,
         voted_up, weighted_vote_score, votes_up),
    )
    conn.commit()


def test_valid_reviews_filters_short_text(db_conn):
    """100자 미만 + 플레이타임 50h 미만 → 제외."""
    _insert_review(db_conn, "r1", 1, "short", playtime_at_review=100)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_passes_long_text(db_conn):
    """100자 이상 → 통과."""
    long_text = "a" * 100
    _insert_review(db_conn, "r1", 1, long_text, playtime_at_review=10)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1


def test_valid_reviews_passes_short_text_high_playtime(db_conn):
    """100자 미만이지만 플레이타임 50h+ → 통과."""
    _insert_review(db_conn, "r1", 1, "good game", playtime_at_review=3000)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1


def test_valid_reviews_excludes_empty_text(db_conn):
    """빈 텍스트 → 제외."""
    _insert_review(db_conn, "r1", 1, "", playtime_at_review=5000)
    _insert_review(db_conn, "r2", 1, "   ", playtime_at_review=5000)
    _insert_review(db_conn, "r3", 1, None, playtime_at_review=5000)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_excludes_ascii_art(db_conn):
    """ASCII art 패턴 포함 → 제외."""
    art = "█" * 200
    _insert_review(db_conn, "r1", 1, art, playtime_at_review=100)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_excludes_null_playtime_short_text(db_conn):
    """playtime NULL + 짧은 텍스트 → 제외."""
    _insert_review(db_conn, "r1", 1, "short", playtime_at_review=None)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 0


def test_valid_reviews_deduplicates_same_game(db_conn):
    """동일 게임 내 동일 텍스트 → weighted_vote_score 최고 1건만 유지."""
    text = "a" * 150
    _insert_review(db_conn, "r1", 1, text, weighted_vote_score=0.3, votes_up=1)
    _insert_review(db_conn, "r2", 1, text, weighted_vote_score=0.9, votes_up=5)
    _insert_review(db_conn, "r3", 1, text, weighted_vote_score=0.6, votes_up=3)
    rows = db_conn.execute("SELECT * FROM valid_reviews WHERE appid=1").fetchall()
    assert len(rows) == 1
    assert rows[0]["recommendation_id"] == "r2"


def test_valid_reviews_keeps_dupes_across_games(db_conn):
    """다른 게임의 동일 텍스트 → 각각 유지."""
    text = "a" * 150
    _insert_review(db_conn, "r1", 1, text, weighted_vote_score=0.5)
    _insert_review(db_conn, "r2", 2, text, weighted_vote_score=0.5)
    rows = db_conn.execute("SELECT * FROM valid_reviews").fetchall()
    assert len(rows) == 2


def test_valid_reviews_survives_reinit(db_path):
    """init_db 두 번 호출해도 View가 정상 동작한다."""
    from steam_crawler.db.schema import init_db

    conn1 = init_db(str(db_path))
    conn1.close()
    conn2 = init_db(str(db_path))
    views = {
        row["name"]
        for row in conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()
    }
    assert "valid_reviews" in views
    conn2.close()
