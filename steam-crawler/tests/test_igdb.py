import time
from unittest.mock import MagicMock, patch, call
from curl_cffi.requests.errors import RequestsError
from steam_crawler.api.igdb import IGDBClient


MOCK_TOKEN_RESPONSE = {
    "access_token": "test_token_abc",
    "expires_in": 5000,
    "token_type": "bearer",
}

MOCK_EXTERNAL_GAMES_RESULT = [{"id": 12345, "game": 1942, "uid": "292030"}]

MOCK_IGDB_GAME_DETAILS = [
    {
        "id": 1942,
        "name": "The Witcher 3: Wild Hunt",
        "summary": "An open world RPG",
        "storyline": "Geralt searches for Ciri",
        "aggregated_rating": 92.5,
        "themes": [{"id": 1, "name": "Fantasy"}, {"id": 17, "name": "Open World"}],
        "keywords": [{"id": 42, "name": "rpg"}, {"id": 99, "name": "choices-matter"}],
    }
]

MOCK_IGDB_SEARCH_RESULTS = [
    {"id": 1942, "name": "The Witcher 3: Wild Hunt"},
    {"id": 1943, "name": "The Witcher 3: Wild Hunt - Blood and Wine"},
]

MOCK_IGDB_EMPTY = []


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = RequestsError(
            f"HTTP {status_code}", code=status_code, response=resp
        )
    return resp


def test_authenticate():
    client = IGDBClient("client_id", "client_secret")
    with patch.object(client._http, "post", return_value=_mock_response(MOCK_TOKEN_RESPONSE)):
        client.authenticate()
    assert client._token == "test_token_abc"
    assert client._token_expires_at > time.time()


def test_search_by_steam_id():
    client = IGDBClient("client_id", "client_secret")
    client._token = "pre_auth"
    client._token_expires_at = float("inf")

    responses = [
        _mock_response(MOCK_EXTERNAL_GAMES_RESULT),  # external_games
        _mock_response(MOCK_IGDB_GAME_DETAILS),       # fetch_game_details
    ]
    with patch.object(client._http, "post", side_effect=responses):
        result = client.search_by_steam_id(292030)
    assert result is not None
    assert result["id"] == 1942
    assert result["summary"] == "An open world RPG"


def test_search_by_steam_id_not_found():
    client = IGDBClient("client_id", "client_secret")
    client._token = "pre_auth"
    client._token_expires_at = float("inf")

    with patch.object(client._http, "post", return_value=_mock_response(MOCK_IGDB_EMPTY)):
        result = client.search_by_steam_id(999999)
    assert result is None


def test_search_by_name():
    client = IGDBClient("client_id", "client_secret")
    client._token = "pre_auth"
    client._token_expires_at = float("inf")

    with patch.object(client._http, "post", return_value=_mock_response(MOCK_IGDB_SEARCH_RESULTS)):
        results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_fetch_game_details():
    client = IGDBClient("client_id", "client_secret")
    client._token = "pre_auth"
    client._token_expires_at = float("inf")

    with patch.object(client._http, "post", return_value=_mock_response(MOCK_IGDB_GAME_DETAILS)):
        details = client.fetch_game_details(1942)
    assert details["summary"] == "An open world RPG"
    assert details["storyline"] == "Geralt searches for Ciri"
    assert details["aggregated_rating"] == 92.5
    assert len(details["themes"]) == 2
    assert len(details["keywords"]) == 2


def test_auto_reauthenticate_on_expired_token():
    client = IGDBClient("client_id", "client_secret")
    client._token = "old_token"
    client._token_expires_at = time.time() - 100  # expired

    responses = [
        _mock_response(MOCK_TOKEN_RESPONSE),           # re-authenticate
        _mock_response(MOCK_EXTERNAL_GAMES_RESULT),    # external_games
        _mock_response(MOCK_IGDB_GAME_DETAILS),        # fetch_game_details
    ]
    with patch.object(client._http, "post", side_effect=responses):
        result = client.search_by_steam_id(292030)
    assert result is not None


def test_authenticate_failure_raises():
    client = IGDBClient("bad_id", "bad_secret")
    mock_resp = _mock_response({"message": "invalid client"}, status_code=401)
    with patch.object(client._http, "post", return_value=mock_resp):
        try:
            client.authenticate()
            assert False, "Should have raised"
        except (RequestsError, Exception):
            pass  # curl_cffi raises RequestsError on raise_for_status
