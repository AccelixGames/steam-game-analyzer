"""Tests for HowLongToBeat wrapper."""
from unittest.mock import patch, MagicMock, AsyncMock
from steam_crawler.api.hltb import HLTBClient


def test_search_returns_best_match():
    client = HLTBClient()
    mock_entry = MagicMock()
    mock_entry.similarity = 0.95
    mock_entry.game_id = 12345
    mock_entry.main_story = 25.5
    mock_entry.main_extra = 40.0
    mock_entry.completionist = 80.0

    with patch("steam_crawler.api.hltb._run_async", return_value=[mock_entry]):
        result = client.search("Hades")

    assert result is not None
    assert result["game_id"] == 12345
    assert result["main_story"] == 25.5


def test_search_no_results():
    client = HLTBClient()
    with patch("steam_crawler.api.hltb._run_async", return_value=[]):
        result = client.search("NonExistentGame12345")
    assert result is None


def test_search_low_similarity_rejected():
    client = HLTBClient()
    mock_entry = MagicMock()
    mock_entry.similarity = 0.2
    mock_entry.game_id = 99
    mock_entry.main_story = 10.0
    mock_entry.main_extra = 20.0
    mock_entry.completionist = 30.0

    with patch("steam_crawler.api.hltb._run_async", return_value=[mock_entry]):
        result = client.search("Completely Different Name")
    assert result is None
