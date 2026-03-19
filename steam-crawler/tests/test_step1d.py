from unittest.mock import MagicMock, patch


MOCK_TOKEN = {"access_token": "tok", "expires_in": 5000, "token_type": "bearer"}

MOCK_EXTERNAL_GAMES = [{"id": 999, "game": 1942, "uid": "730"}]

MOCK_IGDB_GAME = [
    {
        "id": 1942,
        "name": "CS2",
        "summary": "A tactical FPS",
        "storyline": "Counter-terrorists fight",
        "aggregated_rating": 88.0,
        "themes": [{"id": 1, "name": "Action"}],
        "keywords": [{"id": 10, "name": "fps"}, {"id": 20, "name": "multiplayer"}],
    }
]


def _setup_game(db_conn):
    from steam_crawler.db.repository import create_version
    version = create_version(db_conn, "tag", "FPS")
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag, first_seen_ver) VALUES (730, 'CS2', 'tag:FPS', ?)",
        (version,),
    )
    db_conn.commit()
    return version


def _make_igdb_client():
    """Create an IGDBClient with pre-set auth token."""
    from steam_crawler.api.igdb import IGDBClient
    client = IGDBClient("cid", "csec")
    client._token = "tok"
    client._token_expires_at = float("inf")
    return client


def test_step1d_enriches_game(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    client = _make_igdb_client()

    responses = [
        _mock_response(MOCK_EXTERNAL_GAMES),  # external_games
        _mock_response(MOCK_IGDB_GAME),        # fetch_game_details
    ]
    with patch.object(client._http, "post", side_effect=responses):
        count = run_step1d(
            db_conn, version=version, source_tag="tag:FPS",
            igdb_client=client,
        )
    assert count == 1

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == 1942
    assert row["igdb_summary"] == "A tactical FPS"
    assert row["igdb_rating"] == 88.0

    themes = db_conn.execute(
        "SELECT t.name FROM game_themes gt JOIN theme_catalog t ON gt.theme_id=t.id WHERE gt.appid=730"
    ).fetchall()
    assert len(themes) == 1
    assert themes[0]["name"] == "Action"

    keywords = db_conn.execute(
        "SELECT k.name FROM game_keywords gk JOIN keyword_catalog k ON gk.keyword_id=k.id WHERE gk.appid=730"
    ).fetchall()
    assert len(keywords) == 2


def test_step1d_skips_already_enriched(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    db_conn.execute("UPDATE games SET igdb_id=1942 WHERE appid=730")
    db_conn.commit()

    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id="cid", client_secret="csec",
    )
    assert count == 0


def test_step1d_name_fallback(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    client = _make_igdb_client()

    responses = [
        _mock_response([]),  # steam_id search empty
        _mock_response([     # name search
            {"id": 1942, "name": "CS2", "summary": "Found by name",
             "themes": [], "keywords": []},
        ]),
        _mock_response([     # fetch_game_details
            {"id": 1942, "name": "CS2", "summary": "Found by name",
             "aggregated_rating": 85.0, "themes": [], "keywords": []},
        ]),
    ]
    with patch.object(client._http, "post", side_effect=responses):
        count = run_step1d(
            db_conn, version=version, source_tag="tag:FPS",
            igdb_client=client,
        )
    assert count == 1
    row = db_conn.execute("SELECT igdb_summary FROM games WHERE appid=730").fetchone()
    assert row["igdb_summary"] == "Found by name"


def test_step1d_match_failed_marks_unmatchable(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    client = _make_igdb_client()

    responses = [
        _mock_response([]),   # steam_id search empty
        _mock_response([      # name search returns unrelated
            {"id": 999, "name": "Completely Different Game"},
        ]),
    ]
    with patch.object(client._http, "post", side_effect=responses):
        count = run_step1d(
            db_conn, version=version, source_tag="tag:FPS",
            igdb_client=client,
        )
    assert count == 0
    row = db_conn.execute("SELECT igdb_id FROM games WHERE appid=730").fetchone()
    assert row["igdb_id"] == -1

    failures = db_conn.execute(
        "SELECT * FROM failure_logs WHERE failure_type='match_failed'"
    ).fetchall()
    assert len(failures) == 1


def test_step1d_skips_when_no_credentials(db_conn):
    from steam_crawler.pipeline.step1d_igdb import run_step1d

    version = _setup_game(db_conn)
    count = run_step1d(
        db_conn, version=version, source_tag="tag:FPS",
        client_id=None, client_secret=None,
    )
    assert count == 0


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp
