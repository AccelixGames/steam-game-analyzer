from unittest.mock import MagicMock, patch

MOCK_FIRST_PAGE = {
    "success": 1,
    "query_summary": {
        "num_reviews": 2, "review_score": 8,
        "review_score_desc": "Very Positive",
        "total_positive": 5000, "total_negative": 500, "total_reviews": 5500,
    },
    "reviews": [
        {
            "recommendationid": "r1", "language": "english",
            "review": "Amazing game!", "voted_up": True,
            "steam_purchase": True, "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000000, "votes_up": 10, "votes_funny": 2,
            "weighted_vote_score": "0.95", "comment_count": 1,
            "author": {"steamid": "76561198000000001", "num_reviews": 30,
                       "playtime_forever": 5000, "playtime_at_review": 2000},
        },
        {
            "recommendationid": "r2", "language": "english",
            "review": "Not bad", "voted_up": True,
            "steam_purchase": True, "received_for_free": False,
            "written_during_early_access": False,
            "timestamp_created": 1700000001, "votes_up": 5, "votes_funny": 0,
            "weighted_vote_score": "0.80", "comment_count": 0,
            "author": {"steamid": "76561198000000002", "num_reviews": 10,
                       "playtime_forever": 3000, "playtime_at_review": 1000},
        },
    ],
    "cursor": "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg==",
}

MOCK_EMPTY_PAGE = {"success": 1, "reviews": [], "cursor": "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg=="}


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_review_summary():
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    client = SteamReviewsClient()
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_FIRST_PAGE)):
        summary = client.fetch_summary(appid=730)
    assert summary.total_positive == 5000
    assert summary.total_negative == 500
    assert summary.review_score_desc == "Very Positive"


def test_fetch_reviews_page():
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    client = SteamReviewsClient()
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_FIRST_PAGE)):
        reviews, next_cursor, has_more = client.fetch_reviews_page(appid=730, cursor="*")
    assert len(reviews) == 2
    assert reviews[0].recommendation_id == "r1"
    assert reviews[0].appid == 730
    assert next_cursor == "AoMFQFQ3YCAAAAAFP+6dmQAAAAB3gvzABg=="
    assert has_more is True


def test_fetch_reviews_page_empty_means_done():
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    client = SteamReviewsClient()
    with patch.object(client._client, "get", return_value=_mock_response(MOCK_EMPTY_PAGE)):
        reviews, next_cursor, has_more = client.fetch_reviews_page(appid=730, cursor="somecursor")
    assert len(reviews) == 0
    assert has_more is False


def test_reviews_client_uses_correct_params():
    from steam_crawler.api.steam_reviews import SteamReviewsClient
    client = SteamReviewsClient()
    mock_resp = _mock_response(MOCK_FIRST_PAGE)
    with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
        client.fetch_reviews_page(appid=730, cursor="*", language="korean", review_type="positive")
    # Verify the params passed to get()
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    params = call_kwargs[1].get("params") if call_kwargs[1] else call_kwargs[0][1]
    assert params["filter"] == "recent"
    assert params["purchase_type"] == "all"
    assert params["num_per_page"] == "80"
    assert params["language"] == "korean"
    assert params["review_type"] == "positive"
