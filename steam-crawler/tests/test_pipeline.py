import json

import pytest


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


def _create_version(db_conn):
    """Helper to create a data_versions entry for FK constraints."""
    from steam_crawler.db.repository import create_version
    return create_version(db_conn, "tag", "FPS")


def test_step1_collect(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1

    version = _create_version(db_conn)
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    result = run_step1(
        db_conn, query_type="tag", query_value="FPS", limit=2, version=version
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


def test_step1b_enrich(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step1b_enrich import run_step1b

    version = _create_version(db_conn)
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version)
    httpx_mock.add_response(json=MOCK_APPDETAILS_730)
    run_step1b(db_conn, version=version, source_tag="tag:FPS")
    row = db_conn.execute("SELECT tags FROM games WHERE appid=730").fetchone()
    tags = json.loads(row["tags"])
    assert "FPS" in tags


def test_step2_scan(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step2_scan import run_step2

    version = _create_version(db_conn)
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version)
    httpx_mock.add_response(json=MOCK_SUMMARY_RESPONSE)
    run_step2(db_conn, version=version, source_tag="tag:FPS")
    row = db_conn.execute(
        "SELECT steam_positive, review_score FROM games WHERE appid=730"
    ).fetchone()
    assert row["steam_positive"] == 7100000
    assert row["review_score"] == "Overwhelmingly Positive"


def test_step3_crawl(httpx_mock, db_conn):
    from steam_crawler.pipeline.step1_collect import run_step1
    from steam_crawler.pipeline.step3_crawl import run_step3

    version = _create_version(db_conn)
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    run_step1(db_conn, query_type="tag", query_value="FPS", limit=1, version=version)
    httpx_mock.add_response(json=MOCK_REVIEWS_PAGE)
    httpx_mock.add_response(json=MOCK_EMPTY_PAGE)
    run_step3(db_conn, version=version, source_tag="tag:FPS", top_n=1, max_reviews=10)
    reviews = db_conn.execute(
        "SELECT * FROM reviews WHERE appid=730"
    ).fetchall()
    assert len(reviews) == 1
    changelog = db_conn.execute(
        "SELECT * FROM changelog WHERE change_type='reviews_batch_added'"
    ).fetchall()
    assert len(changelog) == 1
