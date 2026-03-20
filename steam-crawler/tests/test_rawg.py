from unittest.mock import MagicMock, patch
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


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def test_search_by_name():
    client = RAWGClient(api_key="test_key")
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_RAWG_SEARCH)):
        results = client.search_by_name("The Witcher 3")
    assert len(results) == 2
    assert results[0]["name"] == "The Witcher 3: Wild Hunt"


def test_search_by_name_empty():
    client = RAWGClient(api_key="test_key")
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_RAWG_EMPTY)):
        results = client.search_by_name("nonexistent game xyz")
    assert results == []


def test_fetch_game_details():
    client = RAWGClient(api_key="test_key")
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_RAWG_DETAILS)):
        details = client.fetch_game_details(3328)
    assert details["description_raw"] == "An RPG with open world exploration and a rich story."
    assert details["metacritic"] == 92
    assert details["rating"] == 4.66


def test_search_by_steam_id():
    client = RAWGClient(api_key="test_key")
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_RAWG_SEARCH)) as mock_get:
        results = client.search_by_steam_id(292030)
    assert len(results) >= 1
    # Verify stores=1 was in the params
    call_kwargs = mock_get.call_args
    params = call_kwargs[1].get("params") if call_kwargs[1] else call_kwargs[0][1]
    assert params.get("stores") == 1 or params.get("stores") == "1" or "stores" in str(params)


def test_api_key_in_params():
    client = RAWGClient(api_key="my_secret_key")
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_RAWG_EMPTY)) as mock_get:
        client.search_by_name("test")
    call_kwargs = mock_get.call_args
    params = call_kwargs[1].get("params") if call_kwargs[1] else call_kwargs[0][1]
    assert params.get("key") == "my_secret_key"
