import json


MOCK_TAG_RESPONSE = {
    "730": {
        "appid": 730,
        "name": "CS2",
        "positive": 7000000,
        "negative": 1000000,
        "owners": "50M",
        "average_forever": 30000,
        "price": "0",
        "score_rank": "",
        "userscore": 0,
        "developer": "Valve",
        "publisher": "Valve",
    },
}
MOCK_APPDETAILS = {
    "appid": 730,
    "name": "CS2",
    "positive": 7000000,
    "negative": 1000000,
    "owners": "50M",
    "average_forever": 30000,
    "price": "0",
    "tags": {"FPS": 90000},
    "score_rank": "",
    "userscore": 0,
}
MOCK_SUMMARY = {
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
MOCK_REVIEWS = {
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
    "cursor": "next==",
}
MOCK_EMPTY = {"success": 1, "reviews": [], "cursor": "next=="}


def test_run_pipeline_full(httpx_mock, db_conn):
    from steam_crawler.pipeline.runner import run_pipeline

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    httpx_mock.add_response(json=MOCK_APPDETAILS)
    httpx_mock.add_response(json=MOCK_SUMMARY)
    httpx_mock.add_response(json=MOCK_REVIEWS)
    httpx_mock.add_response(json=MOCK_EMPTY)
    run_pipeline(
        db_conn,
        query_type="tag",
        query_value="FPS",
        limit=1,
        top_n=1,
        max_reviews=10,
    )
    ver = db_conn.execute(
        "SELECT * FROM data_versions WHERE version=1"
    ).fetchone()
    assert ver["status"] == "completed"
    stats = db_conn.execute("SELECT * FROM rate_limit_stats").fetchall()
    assert len(stats) >= 2


def test_run_pipeline_uses_learned_delays(httpx_mock, db_conn):
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter, save_rate_stats
    from steam_crawler.db.repository import create_version
    from steam_crawler.pipeline.runner import run_pipeline

    prev_ver = create_version(db_conn, "tag", "FPS")
    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=800)
    save_rate_stats(db_conn, rl, session_id=prev_ver)

    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    httpx_mock.add_response(json=MOCK_APPDETAILS)
    httpx_mock.add_response(json=MOCK_SUMMARY)
    httpx_mock.add_response(json=MOCK_REVIEWS)
    httpx_mock.add_response(json=MOCK_EMPTY)
    run_pipeline(
        db_conn,
        query_type="tag",
        query_value="FPS",
        limit=1,
        top_n=1,
        max_reviews=10,
    )
    stats = db_conn.execute(
        "SELECT optimal_delay_ms FROM rate_limit_stats WHERE api_name='steamspy' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert stats is not None
