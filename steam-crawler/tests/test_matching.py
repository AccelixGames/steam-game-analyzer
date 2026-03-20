from steam_crawler.api.matching import GameMatcher


def test_name_similarity_exact():
    m = GameMatcher()
    assert m.name_similarity("Hades", "Hades") == 1.0


def test_name_similarity_case_insensitive():
    m = GameMatcher()
    assert m.name_similarity("hades", "Hades") == 1.0


def test_name_similarity_partial():
    m = GameMatcher()
    score = m.name_similarity("Slay the Spire", "Slay the Spire: Downfall")
    assert 0.6 < score < 1.0


def test_name_similarity_unrelated():
    m = GameMatcher()
    score = m.name_similarity("Hades", "Grand Theft Auto V")
    assert score < 0.5


def test_best_match_above_threshold():
    m = GameMatcher()
    candidates = [
        {"id": 1, "name": "Hades"},
        {"id": 2, "name": "Hades II"},
        {"id": 3, "name": "Stardew Valley"},
    ]
    result = m.best_match("Hades", candidates)
    assert result is not None
    assert result["id"] == 1


def test_best_match_returns_none_below_threshold():
    m = GameMatcher()
    candidates = [
        {"id": 1, "name": "Completely Different Game"},
        {"id": 2, "name": "Another Unrelated Title"},
    ]
    result = m.best_match("Hades", candidates)
    assert result is None


def test_best_match_empty_candidates():
    m = GameMatcher()
    result = m.best_match("Hades", [])
    assert result is None
