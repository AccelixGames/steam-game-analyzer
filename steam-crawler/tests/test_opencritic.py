"""Tests for OpenCritic API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.opencritic import OpenCriticClient


def test_search_and_fetch():
    client = OpenCriticClient(rapidapi_key="test_key")

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = [
        {"id": 42, "name": "Hades", "dist": 0}
    ]

    fetch_resp = MagicMock()
    fetch_resp.status_code = 200
    fetch_resp.json.return_value = {
        "id": 42,
        "topCriticScore": 93.5,
        "percentRecommended": 97.0,
        "tier": "Mighty",
        "numReviews": 120,
    }

    with patch.object(client, "get", side_effect=[search_resp, fetch_resp]):
        matched = client.search("Hades")
        assert matched is not None
        details = client.fetch_game(matched["id"])
        assert details["topCriticScore"] == 93.5
        assert details["tier"] == "Mighty"


def test_search_no_results():
    client = OpenCriticClient(rapidapi_key="test_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search("NonExistent12345")
    assert result is None
