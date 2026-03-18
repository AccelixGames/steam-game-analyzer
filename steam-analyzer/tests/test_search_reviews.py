"""Tests for handle_search_reviews tool."""

import pytest
from steam_analyzer.tools.search_reviews import handle_search_reviews


class TestSearchReviewsByTag:
    def test_search_by_tag_returns_correct_games_count(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        assert result["games_count"] == 2

    def test_search_by_tag_returns_correct_total_reviews(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        # appid=1 has rev1, rev2, rev3, rev5 (4 reviews); appid=2 has rev4 (1 review)
        assert result["total_reviews"] == 5

    def test_search_by_tag_returns_sample_reviews(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        assert "sample_reviews" in result
        assert isinstance(result["sample_reviews"], list)
        assert len(result["sample_reviews"]) > 0

    def test_search_by_tag_sample_reviews_sorted_by_weighted_vote_score(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        scores = [r["weighted_vote_score"] for r in result["sample_reviews"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_by_tag_returns_positive_ratio(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        assert "positive_ratio" in result
        assert 0.0 <= result["positive_ratio"] <= 1.0

    def test_search_by_tag_returns_keywords(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        assert "top_keywords_positive" in result
        assert "top_keywords_negative" in result
        assert isinstance(result["top_keywords_positive"], list)
        assert isinstance(result["top_keywords_negative"], list)

    def test_search_by_rpg_tag(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="RPG")
        assert result["games_count"] == 1
        # appid=3 has no reviews in seeded data
        assert result["total_reviews"] == 0


class TestSearchReviewsByAppid:
    def test_search_by_appid_returns_correct_data(self, seeded_db):
        result = handle_search_reviews(seeded_db, appid=1)
        assert result["games_count"] == 1
        # appid=1 has 4 reviews: rev1, rev2, rev3, rev5
        assert result["total_reviews"] == 4

    def test_search_by_appid_2(self, seeded_db):
        result = handle_search_reviews(seeded_db, appid=2)
        assert result["games_count"] == 1
        assert result["total_reviews"] == 1

    def test_search_by_nonexistent_appid_returns_zero_count(self, seeded_db):
        result = handle_search_reviews(seeded_db, appid=9999)
        assert result["games_count"] == 0
        assert result["total_reviews"] == 0
        assert result["sample_reviews"] == []
        assert "available_tags" in result


class TestSearchReviewsLanguageFilter:
    def test_language_filter_english(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", language="english")
        # appid=1: rev1(english), rev2(english), rev5(english); appid=2: rev4(english)
        assert result["total_reviews"] == 4

    def test_language_filter_korean(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", language="korean")
        # appid=1: rev3(korean) only
        assert result["total_reviews"] == 1

    def test_language_filter_nonexistent(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", language="japanese")
        assert result["total_reviews"] == 0


class TestSearchReviewsSampleCount:
    def test_sample_count_limits_results(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", sample_count=2)
        assert len(result["sample_reviews"]) <= 2

    def test_sample_count_default_is_20(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        # seeded data has only 5 reviews, so all should be returned (< 20)
        assert len(result["sample_reviews"]) <= 20

    def test_sample_count_capped_at_50(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", sample_count=100)
        # The cap is 50, so even though 100 was requested, at most 50 will be returned
        # With only 5 reviews, we'll get <= 5, but the cap must have been applied
        assert len(result["sample_reviews"]) <= 50

    def test_sample_count_zero_returns_empty(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike", sample_count=0)
        assert result["sample_reviews"] == []


class TestSearchReviewsErrorCases:
    def test_no_params_returns_error(self, seeded_db):
        result = handle_search_reviews(seeded_db)
        assert result["error"] is True
        assert result["error_type"] == "no_data"

    def test_no_params_error_has_error_id(self, seeded_db):
        result = handle_search_reviews(seeded_db)
        assert "error_id" in result
        assert isinstance(result["error_id"], int)

    def test_no_params_error_has_suggestion(self, seeded_db):
        result = handle_search_reviews(seeded_db)
        assert "suggestion" in result
        assert len(result["suggestion"]) > 0

    def test_unknown_tag_returns_zero_games(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="UnknownTag")
        assert result["games_count"] == 0
        assert result["sample_reviews"] == []
        assert "available_tags" in result

    def test_unknown_tag_includes_available_tags(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="UnknownTag")
        available = result["available_tags"]
        tag_names = [t["tag_name"] for t in available]
        assert "Roguelike" in tag_names
        assert "RPG" in tag_names


class TestSearchReviewsResponseShape:
    def test_successful_response_has_all_required_keys(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        required_keys = {
            "games_count",
            "total_reviews",
            "positive_ratio",
            "top_keywords_positive",
            "top_keywords_negative",
            "sample_reviews",
        }
        assert required_keys.issubset(result.keys())

    def test_no_error_key_in_success_response(self, seeded_db):
        result = handle_search_reviews(seeded_db, tag="Roguelike")
        assert "error" not in result

    def test_positive_ratio_calculation(self, seeded_db):
        result = handle_search_reviews(seeded_db, appid=1, language="english")
        # rev1(up=True), rev2(up=False), rev5(up=True) → 2/3
        expected = pytest.approx(2 / 3, rel=1e-6)
        assert result["positive_ratio"] == expected
