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
    assert tables >= 11
