"""Tests for PCGamingWiki Cargo API client."""
from unittest.mock import MagicMock, patch
from steam_crawler.api.pcgamingwiki import PCGamingWikiClient


def test_fetch_by_appid_success():
    client = PCGamingWikiClient()

    main_resp = MagicMock()
    main_resp.status_code = 200
    main_resp.json.return_value = {
        "cargoquery": [{"title": {
            "page": "Hades",
            "engines": "Supergiant Engine",
            "steam appid": "1145360",
        }}]
    }

    video_resp = MagicMock()
    video_resp.status_code = 200
    video_resp.json.return_value = {
        "cargoquery": [{"title": {
            "ultrawide": "true",
            "hdr": "false",
            "api": "DirectX 11",
        }}]
    }

    input_resp = MagicMock()
    input_resp.status_code = 200
    input_resp.json.return_value = {
        "cargoquery": [{"title": {"controller": "true"}}]
    }

    with patch.object(client, "get", side_effect=[main_resp, video_resp, input_resp]):
        result = client.fetch_by_appid(1145360)

    assert result is not None
    assert result["engine"] == "Supergiant Engine"
    assert result["has_ultrawide"] is True
    assert result["has_hdr"] is False
    assert result["has_controller"] is True
    assert result["graphics_api"] == "DirectX 11"


def test_fetch_by_appid_not_found():
    client = PCGamingWikiClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"cargoquery": []}
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_appid(999999999)
    assert result is None
