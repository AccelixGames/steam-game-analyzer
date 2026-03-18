import json


def test_game_summary_from_steamspy_tag_response():
    from steam_crawler.models.game import GameSummary

    raw = {
        "appid": 1091500, "name": "Cyberpunk 2077",
        "developer": "CD PROJEKT RED", "publisher": "CD PROJEKT RED",
        "score_rank": "", "positive": 500000, "negative": 100000,
        "userscore": 0, "owners": "10,000,000 .. 20,000,000",
        "average_forever": 3000, "average_2weeks": 500,
        "median_forever": 2000, "median_2weeks": 300,
        "price": "5999", "initialprice": "5999", "discount": "0", "ccu": 50000,
    }
    game = GameSummary.from_steamspy(raw, source_tag="tag:RPG")
    assert game.appid == 1091500
    assert game.name == "Cyberpunk 2077"
    assert game.positive == 500000
    assert game.price == 5999
    assert game.source_tag == "tag:RPG"
    assert game.tags is None


def test_game_summary_from_steamspy_appdetails():
    from steam_crawler.models.game import GameSummary

    raw = {
        "appid": 1091500, "name": "Cyberpunk 2077",
        "developer": "CD PROJEKT RED", "publisher": "CD PROJEKT RED",
        "score_rank": "90", "positive": 500000, "negative": 100000,
        "userscore": 0, "owners": "10,000,000 .. 20,000,000",
        "average_forever": 3000, "average_2weeks": 500,
        "median_forever": 2000, "median_2weeks": 300,
        "price": "5999", "initialprice": "5999", "discount": "0", "ccu": 50000,
        "tags": {"RPG": 5000, "Open World": 4000},
    }
    game = GameSummary.from_steamspy(raw, source_tag="tag:RPG")
    assert game.tags == {"RPG": 5000, "Open World": 4000}


def test_review_from_steam_api():
    from steam_crawler.models.review import Review

    raw = {
        "recommendationid": "12345", "language": "english",
        "review": "Great game!", "voted_up": True, "steam_purchase": True,
        "received_for_free": False, "written_during_early_access": False,
        "timestamp_created": 1700000000, "votes_up": 10, "votes_funny": 2,
        "weighted_vote_score": "0.95", "comment_count": 3,
        "developer_response": "Thanks!",
        "author": {
            "steamid": "76561198000000000", "num_reviews": 50,
            "playtime_forever": 6000, "playtime_at_review": 3000,
        },
    }
    review = Review.from_steam_api(raw, appid=1091500)
    assert review.recommendation_id == "12345"
    assert review.appid == 1091500
    assert review.review_text == "Great game!"
    assert review.voted_up is True
    assert review.weighted_vote_score == 0.95
    assert review.author_steamid == "76561198000000000"
    assert review.playtime_at_review == 3000
    assert review.dev_response == "Thanks!"


def test_review_summary_from_query_summary():
    from steam_crawler.models.review import ReviewSummary

    raw = {
        "num_reviews": 20, "review_score": 8,
        "review_score_desc": "Very Positive",
        "total_positive": 5000, "total_negative": 500, "total_reviews": 5500,
    }
    summary = ReviewSummary.from_query_summary(raw)
    assert summary.total_positive == 5000
    assert summary.total_negative == 500
    assert summary.review_score_desc == "Very Positive"
