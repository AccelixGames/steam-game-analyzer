"""Tests for Twitch Helix API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.twitch import TwitchClient


def make_client():
    """Create a TwitchClient with mock auth."""
    client = TwitchClient(client_id="test_id", client_secret="test_secret")
    client._token = "test_token"
    client._token_expires_at = float("inf")
    return client


def test_search_game_exact_match():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "999", "name": "Schedule II"},
            {"id": "123", "name": "Schedule I"},
        ]
    }
    with patch.object(client._http, "get", return_value=mock_response):
        result = client.search_game("Schedule I")
    assert result is not None
    assert result["id"] == "123"
    assert result["name"] == "Schedule I"


def test_search_game_no_match():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}
    with patch.object(client._http, "get", return_value=mock_response):
        result = client.search_game("NonExistentGame12345")
    assert result is None


def test_get_live_stats_empty():
    client = make_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}
    with patch.object(client._http, "get", return_value=mock_response):
        stats = client.get_live_stats("123")
    assert stats["stream_count"] == 0
    assert stats["viewer_count"] == 0
    assert stats["top_language"] is None


def test_get_live_stats_aggregation():
    client = make_client()
    streams = [
        {"viewer_count": 100, "language": "en"},
        {"viewer_count": 50, "language": "en"},
        {"viewer_count": 30, "language": "de"},
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": streams, "pagination": {}}
    with patch.object(client._http, "get", return_value=mock_response):
        stats = client.get_live_stats("123")
    assert stats["stream_count"] == 3
    assert stats["viewer_count"] == 180
    assert stats["top_language"] == "en"
    assert stats["lang_distribution"] == {"en": 2, "de": 1}
