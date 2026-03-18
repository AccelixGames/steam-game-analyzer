def test_log_game_added(db_conn):
    from steam_crawler.db.changelog import log_game_added

    log_game_added(db_conn, version=1, appid=730)
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "game_added"
    assert row["version"] == 1


def test_log_game_updated(db_conn):
    from steam_crawler.db.changelog import log_game_updated

    log_game_updated(db_conn, version=1, appid=730, field_name="positive",
                     old_value="100", new_value="200")
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "game_updated"
    assert row["field_name"] == "positive"


def test_log_reviews_batch(db_conn):
    from steam_crawler.db.changelog import log_reviews_batch_added

    log_reviews_batch_added(db_conn, version=1, appid=730, count=50)
    row = db_conn.execute("SELECT * FROM changelog WHERE appid=730").fetchone()
    assert row["change_type"] == "reviews_batch_added"
    assert row["new_value"] == "50"


def test_get_diff_between_versions(db_conn):
    from steam_crawler.db.changelog import (
        log_game_added, log_game_updated, get_version_diff,
    )

    log_game_added(db_conn, version=1, appid=730)
    log_game_added(db_conn, version=1, appid=570)
    log_game_updated(db_conn, version=2, appid=730,
                     field_name="positive", old_value="100", new_value="200")

    diff = get_version_diff(db_conn, version=2)
    assert len(diff) == 1
    assert diff[0]["change_type"] == "game_updated"
