from unittest.mock import MagicMock, patch


MOCK_RAWG_SEARCH = {
    "count": 1,
    "results": [
        {"id": 3328, "name": "CS2", "metacritic": 83, "rating": 4.2,
         "stores": [{"store": {"id": 1, "slug": "steam"}}]},
    ],
}

MOCK_RAWG_DETAILS = {
    "id": 3328,
    "name": "CS2",
    "description_raw": "An iconic tactical shooter.",
    "metacritic": 83,
    "rating": 4.2,
}

MOCK_RAWG_EMPTY = {"count": 0, "results": []}


def _setup_game(db_conn):
    from steam_crawler.db.repository import create_version
    version = create_version(db_conn, "tag", "FPS")
    db_conn.execute(
        "INSERT INTO games (appid, name, source_tag, first_seen_ver) VALUES (730, 'CS2', 'tag:FPS', ?)",
        (version,),
    )
    db_conn.commit()
    return version


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _make_rawg_client():
    """Create a RAWGClient for testing."""
    from steam_crawler.api.rawg import RAWGClient
    return RAWGClient(api_key="test_key")


def test_step1e_enriches_game(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    client = _make_rawg_client()

    responses = [
        _mock_response(MOCK_RAWG_SEARCH),
        _mock_response(MOCK_RAWG_DETAILS),
    ]
    with patch.object(client._client, "get", side_effect=responses):
        count = run_step1e(
            db_conn, version=version, source_tag="tag:FPS", rawg_client=client,
        )
    assert count == 1

    row = db_conn.execute("SELECT * FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == 3328
    assert row["rawg_description"] == "An iconic tactical shooter."
    assert row["rawg_rating"] == 4.2
    assert row["metacritic_score"] == 83


def test_step1e_skips_already_enriched(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    db_conn.execute("UPDATE games SET rawg_id=3328 WHERE appid=730")
    db_conn.commit()

    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key="test_key",
    )
    assert count == 0


def test_step1e_match_failed_marks_unmatchable(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    client = _make_rawg_client()

    with patch.object(client._client, "get", return_value=_mock_response(
        {"count": 1, "results": [
            {"id": 999, "name": "Totally Different Game", "metacritic": None, "rating": 0},
        ]}
    )):
        count = run_step1e(
            db_conn, version=version, source_tag="tag:FPS", rawg_client=client,
        )
    assert count == 0
    row = db_conn.execute("SELECT rawg_id FROM games WHERE appid=730").fetchone()
    assert row["rawg_id"] == -1


def test_step1e_skips_when_no_api_key(db_conn):
    from steam_crawler.pipeline.step1e_rawg import run_step1e

    version = _setup_game(db_conn)
    count = run_step1e(
        db_conn, version=version, source_tag="tag:FPS", api_key=None,
    )
    assert count == 0
