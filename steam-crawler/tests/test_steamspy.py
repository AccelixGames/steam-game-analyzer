import json
import pytest
import httpx


MOCK_TAG_RESPONSE = {
    "730": {
        "appid": 730, "name": "Counter-Strike 2",
        "positive": 7000000, "negative": 1000000,
        "owners": "50,000,000 .. 100,000,000",
        "average_forever": 30000, "price": "0",
        "score_rank": "", "userscore": 0,
        "developer": "Valve", "publisher": "Valve",
    },
    "570": {
        "appid": 570, "name": "Dota 2",
        "positive": 1500000, "negative": 400000,
        "owners": "100,000,000 .. 200,000,000",
        "average_forever": 50000, "price": "0",
        "score_rank": "", "userscore": 0,
        "developer": "Valve", "publisher": "Valve",
    },
}

MOCK_APPDETAILS_RESPONSE = {
    "appid": 730, "name": "Counter-Strike 2",
    "positive": 7000000, "negative": 1000000,
    "owners": "50,000,000 .. 100,000,000",
    "average_forever": 30000, "price": "0",
    "tags": {"FPS": 90000, "Shooter": 65000, "Multiplayer": 55000},
}


def test_fetch_games_by_tag(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    client = SteamSpyClient()
    games = client.fetch_by_tag("FPS")
    assert len(games) == 2
    assert games[0].positive >= games[1].positive
    assert games[0].source_tag == "tag:FPS"


def test_fetch_games_by_tag_with_limit(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    client = SteamSpyClient()
    games = client.fetch_by_tag("FPS", limit=1)
    assert len(games) == 1
    assert games[0].appid == 730


def test_fetch_app_details(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient
    httpx_mock.add_response(json=MOCK_APPDETAILS_RESPONSE)
    client = SteamSpyClient()
    game = client.fetch_app_details(730)
    assert game.tags == {"FPS": 90000, "Shooter": 65000, "Multiplayer": 55000}


def test_fetch_by_genre(httpx_mock):
    from steam_crawler.api.steamspy import SteamSpyClient
    httpx_mock.add_response(json=MOCK_TAG_RESPONSE)
    client = SteamSpyClient()
    games = client.fetch_by_genre("Racing")
    assert len(games) == 2
