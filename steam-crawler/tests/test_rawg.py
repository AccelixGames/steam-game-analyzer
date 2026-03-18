import pytest
from steam_crawler.api.rawg import RAWGClient


MOCK_RAWG_SEARCH = {
    "count": 2,
    "results": [
        {
            "id": 3328,
            "name": "The Witcher 3: Wild Hunt",
            "description_raw": "A detailed description",
            "metacritic": 92,
            "rating": 4.66,
            "stores": [{"store": {"id": 1, "slug": "steam"}}],
        },
        {
            "id": 3329,
            "name": "The Witcher 3: Wild Hunt - GOTY",
            "metacritic": 91,
            "rating": 4.5,
            "stores": [],
        },
    ],
}

MOCK_RAWG_DETAILS = {
    "id": 3328,
    "name": "The Witcher 3: Wild Hunt",
    "description_raw": "An RPG with open world exploration and a rich story.",
    "metacritic": 92,
    "rating": 4.66,
    "stores": [{"store": {"id": 1, "slug": "steam"}, "url": "https://store.steampowered.com/app/292030"}],
}

MOCK_RAWG_EMPTY = {"count": 0, "results": []}


def test_search_by_name(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_SEARCH)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_search_by_name_empty(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_EMPTY)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_name("nonexistent game xyz")
    assert results == []


def test_fetch_game_details(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_DETAILS)
    client = RAWGClient(api_key="test_key")
    details = client.fetch_game_details(3328)
    assert details["description_raw"] == "An RPG with open world exploration and a rich story."
    assert details["metacritic"] == 92
    assert details["rating"] == 4.66


def test_search_by_steam_id(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_SEARCH)
    client = RAWGClient(api_key="test_key")
    results = client.search_by_steam_id(292030)
    assert len(results) >= 1
    request = httpx_mock.get_requests()[0]
    assert "stores=1" in str(request.url)


def test_api_key_in_params(httpx_mock):
    httpx_mock.add_response(json=MOCK_RAWG_EMPTY)
    client = RAWGClient(api_key="my_secret_key")
    client.search_by_name("test")
    request = httpx_mock.get_requests()[0]
    assert "key=my_secret_key" in str(request.url)
