"""Tests for Wikidata SPARQL client."""
import pytest
from unittest.mock import MagicMock, patch
from steam_crawler.api.wikidata import WikidataClient


def test_fetch_by_appid_success():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": {
            "bindings": [
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P136"},
                    "val": {"value": "http://www.wikidata.org/entity/Q60053"},
                    "valLabel": {"value": "roguelite"},
                },
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P4151"},
                    "val": {"value": "http://www.wikidata.org/entity/Q22808320"},
                    "valLabel": {"value": "fishing minigame"},
                },
                {
                    "game": {"value": "http://www.wikidata.org/entity/Q63952889"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P674"},
                    "val": {"value": "http://www.wikidata.org/entity/Q41410"},
                    "valLabel": {"value": "Zeus"},
                },
            ]
        }
    }
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_steam_appid(1145360)

    assert result is not None
    assert result["wikidata_id"] == "Q63952889"
    assert len(result["claims"]) == 3
    types = {c["claim_type"] for c in result["claims"]}
    assert "genre" in types
    assert "mechanic" in types
    assert "character" in types


def test_fetch_by_appid_not_found():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": {"bindings": []}}
    with patch.object(client, "get", return_value=mock_resp):
        result = client.fetch_by_steam_appid(999999999)
    assert result is None


def test_fetch_by_appid_http_error():
    client = WikidataClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch.object(client, "get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            client.fetch_by_steam_appid(1145360)
