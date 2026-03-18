from steam_crawler.models.game import GameSummary
from steam_crawler.models.review import Review


def test_upsert_game_insert(db_conn):
    from steam_crawler.db.repository import upsert_game

    game = GameSummary(appid=730, name="CS2", positive=100, negative=10, source_tag="tag:FPS")
    is_new, changes = upsert_game(db_conn, game, version=1)
    assert is_new is True
    assert changes == {}

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["name"] == "CS2"
    assert row["source_tag"] == "tag:FPS"


def test_upsert_game_update_detects_changes(db_conn):
    from steam_crawler.db.repository import upsert_game

    game1 = GameSummary(appid=730, name="CS2", positive=100, negative=10)
    upsert_game(db_conn, game1, version=1)

    game2 = GameSummary(appid=730, name="CS2", positive=200, negative=10)
    is_new, changes = upsert_game(db_conn, game2, version=2)
    assert is_new is False
    assert "positive" in changes
    assert changes["positive"] == ("100", "200")


def test_insert_reviews_batch(db_conn):
    from steam_crawler.db.repository import upsert_game, insert_reviews_batch

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)

    reviews = [
        Review(recommendation_id="r1", appid=730, review_text="Good", voted_up=True),
        Review(recommendation_id="r2", appid=730, review_text="Bad", voted_up=False),
    ]
    inserted = insert_reviews_batch(db_conn, reviews, version=1)
    assert inserted == 2

    row = db_conn.execute("SELECT collected_ver FROM reviews WHERE recommendation_id='r1'").fetchone()
    assert row["collected_ver"] == 1

    count = db_conn.execute("SELECT count(*) FROM reviews WHERE appid=730").fetchone()[0]
    assert count == 2


def test_insert_reviews_ignores_duplicates(db_conn):
    from steam_crawler.db.repository import upsert_game, insert_reviews_batch

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)

    reviews = [Review(recommendation_id="r1", appid=730, review_text="Good")]
    insert_reviews_batch(db_conn, reviews, version=1)
    inserted = insert_reviews_batch(db_conn, reviews, version=1)
    assert inserted == 0


def test_create_version(db_conn):
    from steam_crawler.db.repository import create_version

    ver = create_version(db_conn, query_type="tag", query_value="Roguelike", config="{}")
    assert ver == 1

    row = db_conn.execute("SELECT * FROM data_versions WHERE version=1").fetchone()
    assert row["query_type"] == "tag"
    assert row["status"] == "running"


def test_update_game_review_stats(db_conn):
    from steam_crawler.db.repository import upsert_game, update_game_review_stats

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)
    update_game_review_stats(db_conn, appid=730, steam_positive=5000, steam_negative=500, review_score="Very Positive")

    row = db_conn.execute("SELECT steam_positive, review_score FROM games WHERE appid=730").fetchone()
    assert row["steam_positive"] == 5000
    assert row["review_score"] == "Very Positive"
