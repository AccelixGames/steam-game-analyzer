import pytest
from unittest.mock import MagicMock, patch


MOCK_TAG_RESPONSE = {
    "730": {
        "appid": 730,
        "name": "CS2",
        "positive": 7000000,
        "negative": 1000000,
        "owners": "50,000,000 .. 100,000,000",
        "average_forever": 30000,
        "price": "0",
        "score_rank": "",
        "userscore": 0,
        "developer": "Valve",
        "publisher": "Valve",
    },
    "570": {
        "appid": 570,
        "name": "Dota 2",
        "positive": 1500000,
        "negative": 400000,
        "owners": "100,000,000 .. 200,000,000",
        "average_forever": 50000,
        "price": "0",
        "score_rank": "",
        "userscore": 0,
        "developer": "Valve",
        "publisher": "Valve",
    },
}

MOCK_APPDETAILS_730 = {
    "appid": 730,
    "name": "CS2",
    "positive": 7000000,
    "negative": 1000000,
    "owners": "50,000,000 .. 100,000,000",
    "average_forever": 30000,
    "price": "0",
    "score_rank": "",
    "userscore": 0,
    "tags": {"FPS": 90000, "Shooter": 65000},
    "genre": "Action, Free To Play",
}

MOCK_SUMMARY_RESPONSE = {
    "success": 1,
    "query_summary": {
        "num_reviews": 0,
        "review_score": 9,
        "review_score_desc": "Overwhelmingly Positive",
        "total_positive": 7100000,
        "total_negative": 1050000,
        "total_reviews": 8150000,
    },
    "reviews": [],
    "cursor": "*",
}

MOCK_REVIEWS_PAGE = {
    "success": 1,
    "reviews": [
        {
            "recommendationid": "r1",
            "language": "english",
            "review": "Great!",
            "voted_up": True,
            "steam_purchase": True,
            "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000000,
            "votes_up": 10,
            "votes_funny": 0,
            "weighted_vote_score": "0.9",
            "comment_count": 0,
            "author": {
                "steamid": "123",
                "num_reviews": 5,
                "playtime_forever": 1000,
                "playtime_at_review": 500,
            },
        },
    ],
    "cursor": "nextcursor==",
}

MOCK_EMPTY_PAGE = {"success": 1, "reviews": [], "cursor": "nextcursor=="}


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _create_version(db_conn):
    """Helper to create a data_versions entry for FK constraints."""
    from steam_crawler.db.repository import create_version
    return create_version(db_conn, "tag", "FPS")


def test_step1_collect(db_conn):
    from steam_crawler.api.steamspy import SteamSpyClient
    from steam_crawler.pipeline.step1_collect import run_step1

    version = _create_version(db_conn)
    client = SteamSpyClient()
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_TAG_RESPONSE)):
        result = run_step1(
            db_conn, query_type="tag", query_value="FPS", limit=2, version=version,
            steamspy_client=client,
        )
    assert result == 2
    games = db_conn.execute(
        "SELECT * FROM games ORDER BY positive DESC"
    ).fetchall()
    assert len(games) == 2
    assert games[0]["appid"] == 730
    changelog = db_conn.execute(
        "SELECT * FROM changelog WHERE change_type='game_added'"
    ).fetchall()
    assert len(changelog) == 2


def test_step1_appids_mode(db_conn):
    """step1이 query_type='appids'로 개별 게임을 수집한다."""
    from unittest.mock import MagicMock
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.models.game import GameSummary

    version = _create_version(db_conn)
    mock_client = MagicMock()
    mock_client.fetch_app_details.return_value = GameSummary(
        appid=526870, name="Satisfactory", positive=149000, negative=3900,
        owners="10M", avg_playtime=3000, price=2799,
        score_rank=None, tags=None, genres=None,
        source_tag=None,
    )

    count = run_step1(
        db_conn, query_type="appids", query_value="526870",
        limit=50, version=version, steamspy_client=mock_client,
    )

    assert count == 1
    mock_client.fetch_app_details.assert_called_once_with(526870)
    row = db_conn.execute("SELECT name, source_tag FROM games WHERE appid=526870").fetchone()
    assert row["name"] == "Satisfactory"
    assert row["source_tag"] == "appids:526870"


def test_step1_appids_multiple(db_conn):
    """step1이 복수 appids를 처리한다."""
    from unittest.mock import MagicMock
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.models.game import GameSummary

    version = _create_version(db_conn)
    mock_client = MagicMock()
    mock_client.fetch_app_details.side_effect = [
        GameSummary(appid=526870, name="Satisfactory"),
        GameSummary(appid=427520, name="Factorio"),
    ]

    count = run_step1(
        db_conn, query_type="appids", query_value="526870,427520",
        limit=50, version=version, steamspy_client=mock_client,
    )

    assert count == 2
    assert mock_client.fetch_app_details.call_count == 2


def test_step1b_enrich(db_conn):
    from steam_crawler.api.steamspy import SteamSpyClient
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step1b_enrich import run_step1b

    version = _create_version(db_conn)
    client = SteamSpyClient()

    with patch.object(client._client, "get", return_value=_mock_response(MOCK_TAG_RESPONSE)):
        run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version,
                  steamspy_client=client)

    with patch.object(client._client, "get", return_value=_mock_response(MOCK_APPDETAILS_730)):
        run_step1b(db_conn, version=version, source_tag="tag:FPS", steamspy_client=client)

    tags = db_conn.execute(
        "SELECT tag_name, vote_count FROM game_tags WHERE appid=730 ORDER BY vote_count DESC"
    ).fetchall()
    tag_names = [t["tag_name"] for t in tags]
    assert "FPS" in tag_names
    assert "Shooter" in tag_names

    genres = db_conn.execute(
        "SELECT genre_name FROM game_genres WHERE appid=730 ORDER BY genre_name"
    ).fetchall()
    genre_names = [g["genre_name"] for g in genres]
    assert "Action" in genre_names
    assert "Free To Play" in genre_names


def test_step2_scan(db_conn):
    from steam_crawler.api.steamspy import SteamSpyClient
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step2_scan import run_step2

    version = _create_version(db_conn)
    spy_client = SteamSpyClient()
    rev_client = SteamReviewsClient()

    with patch.object(spy_client._client, "get", return_value=_mock_response(MOCK_TAG_RESPONSE)):
        run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version,
                  steamspy_client=spy_client)

    with patch.object(rev_client._client, "get", return_value=_mock_response(MOCK_SUMMARY_RESPONSE)):
        run_step2(db_conn, version=version, source_tag="tag:FPS", reviews_client=rev_client)

    row = db_conn.execute(
        "SELECT steam_positive, review_score FROM games WHERE appid=730"
    ).fetchone()
    assert row["steam_positive"] == 7100000
    assert row["review_score"] == "Overwhelmingly Positive"


def test_step3_crawl(db_conn):
    from steam_crawler.api.steamspy import SteamSpyClient
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step3_crawl import run_step3

    version = _create_version(db_conn)
    spy_client = SteamSpyClient()
    rev_client = SteamReviewsClient()

    with patch.object(spy_client._client, "get", return_value=_mock_response(MOCK_TAG_RESPONSE)):
        run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version,
                  steamspy_client=spy_client)

    responses = [_mock_response(MOCK_REVIEWS_PAGE), _mock_response(MOCK_EMPTY_PAGE)]
    with patch.object(rev_client._client, "get", side_effect=responses):
        run_step3(db_conn, version=version, source_tag="tag:FPS", top_n=1, max_reviews=10,
                  reviews_client=rev_client)

    reviews = db_conn.execute(
        "SELECT * FROM reviews WHERE appid=730"
    ).fetchall()
    assert len(reviews) == 1
    changelog = db_conn.execute(
        "SELECT * FROM changelog WHERE change_type='reviews_batch_added'"
    ).fetchall()
    assert len(changelog) == 1


# ── Negative supplement tests ──────────────────────────────────────────

NEG_REVIEW_PAGE = {
    "success": 1,
    "reviews": [
        {
            "recommendationid": f"supp_neg_{i}", "language": "english",
            "review": f"Bad game {i}", "voted_up": False,
            "steam_purchase": True, "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000000 + i, "votes_up": 1, "votes_funny": 0,
            "weighted_vote_score": "0.5", "comment_count": 0,
            "author": {"steamid": f"supp_{i}", "num_reviews": 1,
                       "playtime_forever": 100, "playtime_at_review": 50},
        }
        for i in range(80)
    ],
    "cursor": "nextcursor==",
}


def _setup_game_for_supplement(db_conn, appid=730, steam_positive=9000, steam_negative=1000,
                                num_positive=900, num_negative=50):
    """부정 보강 테스트용 게임+리뷰 셋업."""
    db_conn.execute("INSERT OR IGNORE INTO games (appid, name, steam_positive, steam_negative) VALUES (?, ?, ?, ?)",
                    (appid, f"Game{appid}", steam_positive, steam_negative))
    for i in range(num_positive):
        db_conn.execute(
            "INSERT OR IGNORE INTO reviews (recommendation_id, appid, review_text, voted_up) VALUES (?, ?, ?, ?)",
            (f"pos_{i}", appid, f"positive review {i}", 1))
    for i in range(num_negative):
        db_conn.execute(
            "INSERT OR IGNORE INTO reviews (recommendation_id, appid, review_text, voted_up) VALUES (?, ?, ?, ?)",
            (f"neg_{i}", appid, f"negative review {i}", 0))
    db_conn.commit()


def test_count_reviews_by_sentiment(db_conn):
    from steam_crawler.pipeline.step3_crawl import _count_reviews_by_sentiment

    _setup_game_for_supplement(db_conn, num_positive=10, num_negative=5)
    pos, neg = _count_reviews_by_sentiment(db_conn, 730)
    assert pos == 10
    assert neg == 5


def test_negative_supplement_runs_when_insufficient(db_conn):
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, num_positive=900, num_negative=50)
    # Create collection status row
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    empty_page = {"success": 1, "reviews": [], "cursor": "nextcursor=="}
    responses = [_mock_response(NEG_REVIEW_PAGE), _mock_response(empty_page)]
    with patch.object(client._client, "get", side_effect=responses) as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added > 0
    # Verify API was called with review_type=negative
    call_args = mock_get.call_args_list[0]
    params = call_args[1].get("params", call_args[0][1] if len(call_args[0]) > 1 else {})
    assert params.get("review_type") == "negative"


def test_negative_supplement_skips_when_sufficient(db_conn):
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=1000,
                                num_positive=500, num_negative=250)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_skips_low_official_negative(db_conn):
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=9000, steam_negative=5,
                                num_positive=100, num_negative=2)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_skips_zero_positive(db_conn):
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, steam_positive=0, steam_negative=100,
                                num_positive=0, num_negative=10)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_updates_review_types_done(db_conn):
    import json
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, num_positive=900, num_negative=50)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    empty_page = {"success": 1, "reviews": [], "cursor": "nextcursor=="}
    responses = [_mock_response(NEG_REVIEW_PAGE), _mock_response(empty_page)]
    with patch.object(client._client, "get", side_effect=responses):
        _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    status = db_conn.execute(
        "SELECT review_types_done FROM game_collection_status WHERE appid=730 AND version=?",
        (version,),
    ).fetchone()
    done_list = json.loads(status["review_types_done"])
    assert "negative_supplement" in done_list


def test_negative_supplement_skips_on_rerun(db_conn):
    import json
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, num_positive=900, num_negative=50)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version, review_types_done) VALUES (?, ?, ?)",
        (730, version, json.dumps(["negative_supplement"])))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    with patch.object(client._client, "get") as mock_get:
        added = _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    assert added == 0
    mock_get.assert_not_called()


def test_negative_supplement_logs_failure(db_conn):
    from steam_crawler.pipeline.step3_crawl import _supplement_negative_reviews
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    from steam_crawler.api.resilience import FailureTracker

    version = _create_version(db_conn)
    _setup_game_for_supplement(db_conn, num_positive=900, num_negative=50)
    db_conn.execute(
        "INSERT OR IGNORE INTO game_collection_status (appid, version) VALUES (?, ?)",
        (730, version))
    db_conn.commit()

    client = SteamReviewsClient()
    tracker = FailureTracker()
    with patch.object(client._client, "get", side_effect=ConnectionError("timeout")):
        _supplement_negative_reviews(db_conn, 730, version, "all", client, tracker)

    failures = db_conn.execute(
        "SELECT * FROM failure_logs WHERE api_name='steam_reviews_negative_supplement'"
    ).fetchall()
    assert len(failures) >= 1
