import time
import pytest
from steam_crawler.api.igdb import IGDBClient


MOCK_TOKEN_RESPONSE = {
    "access_token": "test_token_abc",
    "expires_in": 5000,
    "token_type": "bearer",
}

MOCK_IGDB_GAME_BY_STEAM = [
    {
        "id": 1942,
        "name": "The Witcher 3: Wild Hunt",
        "summary": "An open world RPG",
        "storyline": "Geralt searches for Ciri",
        "aggregated_rating": 92.5,
        "themes": [{"id": 1, "name": "Fantasy"}, {"id": 17, "name": "Open World"}],
        "keywords": [{"id": 42, "name": "rpg"}, {"id": 99, "name": "choices-matter"}],
        "external_games": [{"uid": "292030", "category": 1}],
    }
]

MOCK_IGDB_SEARCH_RESULTS = [
    {"id": 1942, "name": "The Witcher 3: Wild Hunt"},
    {"id": 1943, "name": "The Witcher 3: Wild Hunt - Blood and Wine"},
]

MOCK_IGDB_EMPTY = []


def test_authenticate(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    client = IGDBClient("client_id", "client_secret")
    client.authenticate()
    assert client._token == "test_token_abc"
    assert client._token_expires_at > time.time()


def test_search_by_steam_id(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    client = IGDBClient("client_id", "client_secret")
    result = client.search_by_steam_id(292030)
    assert result is not None
    assert result["id"] == 1942
    assert result["summary"] == "An open world RPG"


def test_search_by_steam_id_not_found(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_EMPTY)
    client = IGDBClient("client_id", "client_secret")
    result = client.search_by_steam_id(999999)
    assert result is None


def test_search_by_name(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_SEARCH_RESULTS)
    client = IGDBClient("client_id", "client_secret")
    results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_fetch_game_details(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    client = IGDBClient("client_id", "client_secret")
    details = client.fetch_game_details(1942)
    assert details["summary"] == "An open world RPG"
    assert details["storyline"] == "Geralt searches for Ciri"
    assert details["aggregated_rating"] == 92.5
    assert len(details["themes"]) == 2
    assert len(details["keywords"]) == 2


def test_auto_reauthenticate_on_expired_token(httpx_mock):
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    client = IGDBClient("client_id", "client_secret")
    client.authenticate()
    client._token_expires_at = time.time() - 100
    httpx_mock.add_response(json=MOCK_TOKEN_RESPONSE)
    httpx_mock.add_response(json=MOCK_IGDB_GAME_BY_STEAM)
    result = client.search_by_steam_id(292030)
    assert result is not None


def test_authenticate_failure_raises(httpx_mock):
    import httpx as httpx_mod
    httpx_mock.add_response(status_code=401, json={"message": "invalid client"})
    client = IGDBClient("bad_id", "bad_secret")
    with pytest.raises(httpx_mod.HTTPStatusError):
        client.authenticate()
