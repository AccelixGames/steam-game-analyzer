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


def test_upsert_game_genres(db_conn):
    from steam_crawler.db.repository import upsert_game, upsert_game_genres

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)
    inserted = upsert_game_genres(db_conn, 730, ["Action", "Free To Play"])
    assert inserted == 2

    rows = db_conn.execute(
        "SELECT genre_name FROM game_genres WHERE appid=730 ORDER BY genre_name"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["genre_name"] == "Action"
    assert rows[1]["genre_name"] == "Free To Play"


def test_upsert_game_tags(db_conn):
    from steam_crawler.db.repository import upsert_game, upsert_game_tags

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)
    tags = {"FPS": 90000, "Shooter": 65000, "Multiplayer": 55000}
    inserted = upsert_game_tags(db_conn, 730, tags)
    assert inserted == 3

    rows = db_conn.execute(
        "SELECT tag_name, vote_count FROM game_tags WHERE appid=730 ORDER BY vote_count DESC"
    ).fetchall()
    assert len(rows) == 3
    assert rows[0]["tag_name"] == "FPS"
    assert rows[0]["vote_count"] == 90000


def test_upsert_game_tags_updates_existing(db_conn):
    from steam_crawler.db.repository import upsert_game, upsert_game_tags

    upsert_game(db_conn, GameSummary(appid=730, name="CS2"), version=1)
    upsert_game_tags(db_conn, 730, {"FPS": 90000})
    upsert_game_tags(db_conn, 730, {"FPS": 95000, "Action": 50000})

    rows = db_conn.execute(
        "SELECT tag_name, vote_count FROM game_tags WHERE appid=730 ORDER BY vote_count DESC"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["tag_name"] == "FPS"
    assert rows[0]["vote_count"] == 95000


def _insert_game(db_conn, appid=730, name="CS2"):
    """Helper to insert a game for FK constraints."""
    db_conn.execute(
        "INSERT INTO games (appid, name) VALUES (?, ?)", (appid, name)
    )
    db_conn.commit()


def test_update_game_igdb_details(db_conn):
    from steam_crawler.db.repository import update_game_igdb_details
    _insert_game(db_conn)
    update_game_igdb_details(
        db_conn, appid=730, igdb_id=12345,
        igdb_summary="A tactical shooter", igdb_storyline="Counter-terrorists vs terrorists",
        igdb_rating=85.5,
    )
    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 12345
    assert row["igdb_summary"] == "A tactical shooter"
    assert row["igdb_storyline"] == "Counter-terrorists vs terrorists"
    assert row["igdb_rating"] == 85.5


def test_update_game_rawg_details(db_conn):
    from steam_crawler.db.repository import update_game_rawg_details
    _insert_game(db_conn)
    update_game_rawg_details(
        db_conn, appid=730, rawg_id=4200,
        rawg_description="A detailed description of the game",
        rawg_rating=4.2, metacritic_score=83,
    )
    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == 4200
    assert row["rawg_description"] == "A detailed description of the game"
    assert row["rawg_rating"] == 4.2
    assert row["metacritic_score"] == 83


def test_upsert_game_themes(db_conn):
    from steam_crawler.db.repository import upsert_game_themes
    _insert_game(db_conn)
    themes = {1: "Horror", 2: "Survival"}
    count = upsert_game_themes(db_conn, appid=730, themes=themes)
    assert count == 2
    rows = db_conn.execute(
        "SELECT t.name FROM game_themes gt JOIN theme_catalog t ON gt.theme_id=t.id WHERE gt.appid=730"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert names == {"Horror", "Survival"}


def test_upsert_game_themes_auto_creates_catalog(db_conn):
    from steam_crawler.db.repository import upsert_game_themes
    _insert_game(db_conn)
    upsert_game_themes(db_conn, appid=730, themes={99: "NewTheme"})
    cat = db_conn.execute("SELECT * FROM theme_catalog WHERE id=99").fetchone()
    assert cat["name"] == "NewTheme"


def test_upsert_game_keywords(db_conn):
    from steam_crawler.db.repository import upsert_game_keywords
    _insert_game(db_conn)
    keywords = {10: "roguelike", 20: "procedural"}
    count = upsert_game_keywords(db_conn, appid=730, keywords=keywords)
    assert count == 2
    rows = db_conn.execute(
        "SELECT k.name FROM game_keywords gk JOIN keyword_catalog k ON gk.keyword_id=k.id WHERE gk.appid=730"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert names == {"roguelike", "procedural"}


def test_get_games_needing_igdb(db_conn):
    from steam_crawler.db.repository import get_games_needing_enrichment
    _insert_game(db_conn, appid=730, name="CS2")
    _insert_game(db_conn, appid=570, name="Dota 2")
    db_conn.execute("UPDATE games SET igdb_id=12345 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="igdb")
    appids = [g["appid"] for g in games]
    assert 570 in appids
    assert 730 not in appids


def test_get_games_needing_rawg(db_conn):
    from steam_crawler.db.repository import get_games_needing_enrichment
    _insert_game(db_conn, appid=730, name="CS2")
    _insert_game(db_conn, appid=570, name="Dota 2")
    db_conn.execute("UPDATE games SET rawg_id=4200 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="rawg")
    appids = [g["appid"] for g in games]
    assert 570 in appids
    assert 730 not in appids


def test_get_games_needing_enrichment_excludes_unmatchable(db_conn):
    from steam_crawler.db.repository import get_games_needing_enrichment
    _insert_game(db_conn, appid=730, name="CS2")
    db_conn.execute("UPDATE games SET igdb_id=-1 WHERE appid=730")
    db_conn.commit()
    games = get_games_needing_enrichment(db_conn, source="igdb")
    assert len(games) == 0


def test_get_games_by_version_appids_filter(db_conn):
    """get_games_by_version should return only specified appids when filter is given."""
    from steam_crawler.db.repository import upsert_game, get_games_by_version
    from steam_crawler.models.game import GameSummary

    for appid, name, pos in [(100, "GameA", 500), (200, "GameB", 300), (300, "GameC", 100)]:
        upsert_game(db_conn, GameSummary(appid=appid, name=name, positive=pos, negative=10), version=0)

    result = get_games_by_version(db_conn, appids=[100, 300])
    returned_ids = [g["appid"] for g in result]

    assert returned_ids == [100, 300]  # sorted by positive DESC
    assert len(result) == 2


def test_get_games_by_version_appids_none_returns_all(db_conn):
    """appids=None should return all games (backward compat)."""
    from steam_crawler.db.repository import upsert_game, get_games_by_version
    from steam_crawler.models.game import GameSummary

    for appid, name, pos in [(100, "GameA", 500), (200, "GameB", 300)]:
        upsert_game(db_conn, GameSummary(appid=appid, name=name, positive=pos, negative=10), version=0)

    result = get_games_by_version(db_conn, appids=None)
    assert len(result) == 2


def test_get_games_by_version_empty_appids_returns_empty(db_conn):
    """appids=[] should return empty list without SQL error."""
    from steam_crawler.db.repository import upsert_game, get_games_by_version
    from steam_crawler.models.game import GameSummary

    upsert_game(db_conn, GameSummary(appid=100, name="GameA", positive=500, negative=10), version=0)

    result = get_games_by_version(db_conn, appids=[])
    assert result == []
