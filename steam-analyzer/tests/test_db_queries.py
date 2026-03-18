"""Tests for db_queries module."""
import pytest


# ---------------------------------------------------------------------------
# get_games_by_tag
# ---------------------------------------------------------------------------

class TestGetGamesByTag:
    def test_returns_games_with_matching_tag(self, seeded_db):
        from steam_analyzer.db_queries import get_games_by_tag

        results = get_games_by_tag(seeded_db, "Roguelike")
        assert len(results) == 2
        appids = {r["appid"] for r in results}
        assert appids == {1, 2}

    def test_returns_dicts(self, seeded_db):
        from steam_analyzer.db_queries import get_games_by_tag

        results = get_games_by_tag(seeded_db, "Roguelike")
        assert isinstance(results, list)
        assert isinstance(results[0], dict)

    def test_result_contains_game_fields(self, seeded_db):
        from steam_analyzer.db_queries import get_games_by_tag

        results = get_games_by_tag(seeded_db, "Roguelike")
        first = results[0]
        assert "appid" in first
        assert "name" in first

    def test_returns_empty_for_unknown_tag(self, seeded_db):
        from steam_analyzer.db_queries import get_games_by_tag

        results = get_games_by_tag(seeded_db, "NonExistentTag")
        assert results == []

    def test_single_game_tag(self, seeded_db):
        from steam_analyzer.db_queries import get_games_by_tag

        results = get_games_by_tag(seeded_db, "RPG")
        assert len(results) == 1
        assert results[0]["appid"] == 3


# ---------------------------------------------------------------------------
# get_reviews_for_games
# ---------------------------------------------------------------------------

class TestGetReviewsForGames:
    def test_returns_reviews_for_given_appids(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [1])
        assert len(results) >= 3  # rev1, rev2, rev3, rev5

    def test_includes_game_name(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [1])
        assert all("game_name" in r for r in results)
        assert results[0]["game_name"] == "Game Alpha"

    def test_multiple_appids(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [1, 2])
        appids = {r["appid"] for r in results}
        assert appids == {1, 2}

    def test_language_filter(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [1], language="korean")
        assert len(results) == 1
        assert results[0]["language"] == "korean"

    def test_language_filter_none_returns_all(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        all_results = get_reviews_for_games(seeded_db, [1])
        filtered = get_reviews_for_games(seeded_db, [1], language=None)
        assert len(all_results) == len(filtered)

    def test_empty_appids_returns_empty(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [])
        assert results == []

    def test_returns_list_of_dicts(self, seeded_db):
        from steam_analyzer.db_queries import get_reviews_for_games

        results = get_reviews_for_games(seeded_db, [1])
        assert isinstance(results, list)
        assert isinstance(results[0], dict)


# ---------------------------------------------------------------------------
# get_review_samples
# ---------------------------------------------------------------------------

class TestGetReviewSamples:
    def test_returns_positive_reviews(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=True, limit=10)
        assert all(r["voted_up"] for r in results)

    def test_returns_negative_reviews(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=False, limit=10)
        assert all(not r["voted_up"] for r in results)

    def test_limit_is_respected(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=True, limit=2)
        assert len(results) <= 2

    def test_ordered_by_weighted_vote_score_desc(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=True, limit=10)
        scores = [r["weighted_vote_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_review_text_truncated_to_500(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        # rev5 has 600-char text and is voted_up=True with score=0.95 (highest)
        results = get_review_samples(seeded_db, [1], voted_up=True, limit=10)
        for r in results:
            assert len(r["review_text"]) <= 500

    def test_language_filter(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=True, limit=10, language="korean")
        assert len(results) == 1
        assert results[0]["language"] == "korean"

    def test_empty_appids_returns_empty(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [], voted_up=True, limit=10)
        assert results == []

    def test_returns_list_of_dicts(self, seeded_db):
        from steam_analyzer.db_queries import get_review_samples

        results = get_review_samples(seeded_db, [1], voted_up=True, limit=10)
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], dict)


# ---------------------------------------------------------------------------
# get_available_tags
# ---------------------------------------------------------------------------

class TestGetAvailableTags:
    def test_returns_all_tags(self, seeded_db):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(seeded_db)
        tag_names = {r["tag_name"] for r in results}
        assert "Roguelike" in tag_names
        assert "RPG" in tag_names
        assert "Action" in tag_names

    def test_includes_game_count(self, seeded_db):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(seeded_db)
        assert all("game_count" in r for r in results)

    def test_game_count_correct(self, seeded_db):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(seeded_db)
        by_tag = {r["tag_name"]: r["game_count"] for r in results}
        assert by_tag["Roguelike"] == 2
        assert by_tag["RPG"] == 1
        assert by_tag["Action"] == 1

    def test_returns_list_of_dicts(self, seeded_db):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(seeded_db)
        assert isinstance(results, list)
        assert isinstance(results[0], dict)

    def test_distinct_tags(self, seeded_db):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(seeded_db)
        tag_names = [r["tag_name"] for r in results]
        assert len(tag_names) == len(set(tag_names))

    def test_empty_db_returns_empty(self, db_conn):
        from steam_analyzer.db_queries import get_available_tags

        results = get_available_tags(db_conn)
        assert results == []
