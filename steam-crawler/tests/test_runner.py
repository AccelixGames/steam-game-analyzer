import json
from unittest.mock import MagicMock, patch


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


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    resp.text = json.dumps(json_data)
    return resp


def _make_get_side_effect(responses):
    """Create a side_effect function from a list of response data dicts."""
    call_counter = {"i": 0}
    mock_responses = [_mock_response(r) for r in responses]

    def side_effect(*args, **kwargs):
        idx = call_counter["i"]
        call_counter["i"] += 1
        if idx < len(mock_responses):
            return mock_responses[idx]
        # Return empty response as fallback
        return _mock_response({"success": 1, "reviews": [], "cursor": "*"})

    return side_effect


def test_run_pipeline_full(db_conn, monkeypatch):
    monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RAWG_API_KEY", raising=False)
    from steam_crawler.pipeline.runner import run_pipeline

    get_responses = [
        MOCK_TAG_RESPONSE,      # step1: fetch by tag
        MOCK_APPDETAILS,        # step1b: app details
        # step1c: store EN + KO (these are also GET calls)
        {"730": {"success": True, "data": {"short_description": "FPS", "screenshots": [], "movies": []}}},
        {"730": {"success": True, "data": {"short_description": "FPS", "screenshots": [], "movies": []}}},
        MOCK_SUMMARY,           # step2: review summary
        MOCK_REVIEWS,           # step3: reviews page 1
        MOCK_EMPTY,             # step3: reviews page 2 (empty)
    ]

    with patch("curl_cffi.requests.Session.get", side_effect=_make_get_side_effect(get_responses)):
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


def test_run_pipeline_uses_learned_delays(db_conn, monkeypatch):
    monkeypatch.delenv("TWITCH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TWITCH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("RAWG_API_KEY", raising=False)
    from steam_crawler.api.rate_limiter import AdaptiveRateLimiter, save_rate_stats
    from steam_crawler.db.repository import create_version
    from steam_crawler.pipeline.runner import run_pipeline

    prev_ver = create_version(db_conn, "tag", "FPS")
    rl = AdaptiveRateLimiter(api_name="steamspy", default_delay_ms=800)
    save_rate_stats(db_conn, rl, session_id=prev_ver)

    get_responses = [
        MOCK_TAG_RESPONSE,
        MOCK_APPDETAILS,
        {"730": {"success": True, "data": {"short_description": "FPS", "screenshots": [], "movies": []}}},
        {"730": {"success": True, "data": {"short_description": "FPS", "screenshots": [], "movies": []}}},
        MOCK_SUMMARY,
        MOCK_REVIEWS,
        MOCK_EMPTY,
    ]

    with patch("curl_cffi.requests.Session.get", side_effect=_make_get_side_effect(get_responses)):
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


def test_runner_calls_step1d_step1e(db_conn, monkeypatch):
    """Runner calls step1d and step1e when env vars are set."""
    monkeypatch.setenv("TWITCH_CLIENT_ID", "test_cid")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "test_csec")
    monkeypatch.setenv("RAWG_API_KEY", "test_key")

    get_responses = [
        # Step1 (SteamSpy tag)
        {"730": {"appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
                 "owners": "50M", "average_forever": 30000, "price": "0", "score_rank": "",
                 "userscore": 0, "developer": "Valve", "publisher": "Valve"}},
        # Step1b (app details)
        {"appid": 730, "name": "CS2", "positive": 7000000, "negative": 1000000,
         "owners": "50M", "average_forever": 30000, "price": "0", "score_rank": "",
         "tags": {"FPS": 90000}, "genre": "Action"},
        # Step1c (store EN)
        {"730": {"success": True, "data": {
            "short_description": "Tactical FPS", "header_image": "img.jpg",
            "screenshots": [], "movies": [],
        }}},
        # Step1c (store KO)
        {"730": {"success": True, "data": {
            "short_description": "FPS", "screenshots": [], "movies": [],
        }}},
        # Step1e (RAWG search) -- RAWG uses BaseClient.get -> Session.get
        {"count": 1, "results": [
            {"id": 3328, "name": "CS2", "metacritic": 83, "rating": 4.2},
        ]},
        # Step1e (RAWG details)
        {"id": 3328, "name": "CS2", "description_raw": "Detailed", "metacritic": 83, "rating": 4.2},
    ]

    post_responses = [
        # Step1d IGDB auth
        {"access_token": "tok", "expires_in": 5000, "token_type": "bearer"},
        # Step1d IGDB external_games lookup
        [{"id": 999, "game": 1942, "uid": "730"}],
        # Step1d IGDB fetch_game_details
        [{"id": 1942, "name": "CS2", "summary": "A FPS", "themes": [], "keywords": []}],
        # Step1f Twitch auth
        {"access_token": "tok2", "expires_in": 5000, "token_type": "bearer"},
    ]

    get_counter = {"i": 0}
    get_mocks = [_mock_response(r) for r in get_responses]

    def get_side_effect(*args, **kwargs):
        idx = get_counter["i"]
        get_counter["i"] += 1
        if idx < len(get_mocks):
            return get_mocks[idx]
        # Twitch get calls for step1f -- return empty data
        return _mock_response({"data": []})

    post_counter = {"i": 0}
    post_mocks = [_mock_response(r) for r in post_responses]

    def post_side_effect(*args, **kwargs):
        idx = post_counter["i"]
        post_counter["i"] += 1
        if idx < len(post_mocks):
            return post_mocks[idx]
        return _mock_response({})

    from steam_crawler.pipeline.runner import run_pipeline
    with patch("curl_cffi.requests.Session.get", side_effect=get_side_effect), \
         patch("curl_cffi.requests.Session.post", side_effect=post_side_effect):
        run_pipeline(db_conn, query_type="tag", query_value="FPS", limit=1, top_n=0, step=1)

    row = db_conn.execute("SELECT igdb_id, rawg_id FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 1942
    assert row["rawg_id"] == 3328
