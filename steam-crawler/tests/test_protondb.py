"""Tests for ProtonDB API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.protondb import ProtonDBClient


def test_fetch_summary_success():
    client = ProtonDBClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tier": "gold",
        "confidence": "good",
        "trendingTier": "gold",
        "total": 42,
        "score": 0.72,
        "bestReportedTier": "platinum",
    }
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_summary(730)
    assert result["tier"] == "gold"
    assert result["total"] == 42


def test_fetch_summary_not_found():
    client = ProtonDBClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_summary(999999999)
    assert result is None
