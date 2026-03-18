import pytest
from steam_analyzer.stats.review_stats import extract_keywords, compute_review_stats


def test_extract_keywords_english():
    texts = ["This is a fun game with great gameplay", "Very fun and exciting game"]
    result = extract_keywords(texts, top_n=30)
    words = [item["word"] for item in result]
    assert "fun" in words
    # stopwords should be excluded
    assert "the" not in words
    assert "and" not in words
    assert "game" not in words
    # each result item has word and count keys
    for item in result:
        assert "word" in item
        assert "count" in item


def test_extract_keywords_filters_short_words():
    texts = ["go to the big world it is ok"]
    result = extract_keywords(texts, top_n=30)
    words = [item["word"] for item in result]
    # 2 chars or fewer should be excluded
    assert "go" not in words
    assert "to" not in words
    assert "it" not in words
    assert "is" not in words
    assert "ok" not in words
    # 3-char words (not stopwords) should be included
    assert "big" in words


def test_extract_keywords_filters_numbers():
    # regex only matches [a-zA-Z\uAC00-\uD7A3]+, so numbers are naturally excluded
    texts = ["player 100 has 999 points and 42 wins"]
    result = extract_keywords(texts, top_n=30)
    words = [item["word"] for item in result]
    assert "100" not in words
    assert "999" not in words
    assert "42" not in words
    # the word "player" should be present (6 chars, not a stopword)
    assert "player" in words


def test_extract_keywords_korean():
    texts = ["재미있는 게임입니다", "정말 재미있고 좋아요"]
    result = extract_keywords(texts, top_n=30)
    words = [item["word"] for item in result]
    # Korean words longer than 2 chars should appear
    assert "재미있는" in words or "재미있고" in words or any(len(w) > 2 for w in words)


def test_extract_keywords_empty():
    result = extract_keywords([], top_n=30)
    assert result == []

    result2 = extract_keywords([""], top_n=30)
    assert result2 == []


def test_compute_review_stats():
    reviews = [
        {"voted_up": True, "review_text": "This game is excellent and fun"},
        {"voted_up": True, "review_text": "Amazing graphics and fun gameplay"},
        {"voted_up": False, "review_text": "Terrible performance and awful bugs"},
        {"voted_up": False, "review_text": "Boring and repetitive terrible design"},
    ]
    result = compute_review_stats(reviews, top_n=30)

    assert result["total_reviews"] == 4
    assert result["positive_ratio"] == pytest.approx(0.5)

    pos_words = [item["word"] for item in result["top_keywords_positive"]]
    assert "fun" in pos_words or "excellent" in pos_words or "amazing" in pos_words

    neg_words = [item["word"] for item in result["top_keywords_negative"]]
    assert "terrible" in neg_words or "boring" in neg_words


def test_compute_review_stats_empty():
    result = compute_review_stats([], top_n=30)
    assert result["total_reviews"] == 0
    assert result["positive_ratio"] == 0.0
    assert result["top_keywords_positive"] == []
    assert result["top_keywords_negative"] == []
