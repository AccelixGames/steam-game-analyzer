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
