"""Tests for CheapShark API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.cheapshark import CheapSharkClient


def test_search_by_steam_appid_success():
    client = CheapSharkClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"gameID": "123", "dealRating": "8.5", "title": "Test Game"}
    ]
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search_by_steam_appid(730)
    assert result is not None
    assert result["dealRating"] == "8.5"


def test_search_by_steam_appid_no_deals():
    client = CheapSharkClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    with patch.object(client, "get", return_value=mock_resp):
        result = client.search_by_steam_appid(999999)
    assert result is None


def test_fetch_game_details():
    client = CheapSharkClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "info": {"title": "Test Game"},
        "cheapestPriceEver": {"price": "4.99", "date": 1609459200},
        "deals": [],
    }
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_game_details("123")
    assert result is not None
    assert result["cheapestPriceEver"]["price"] == "4.99"
