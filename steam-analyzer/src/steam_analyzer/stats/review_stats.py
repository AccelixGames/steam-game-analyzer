"""Review statistics and keyword extraction for Steam game reviews."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

ENGLISH_STOPWORDS: frozenset[str] = frozenset({
    # Common English stopwords
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know",
    "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how",
    "our", "work", "first", "well", "way", "even", "new", "want", "because",
    "any", "these", "give", "day", "most", "us", "was", "are", "were",
    "has", "had", "been", "did", "does", "got", "may", "too", "very",
    "much", "more", "such", "own", "off", "don", "here", "while",
    # Game-specific stopwords
    "game", "games", "play", "played", "playing",
})

KOREAN_STOPWORDS: frozenset[str] = frozenset({
    # Common Korean particles/postpositions
    "이", "가", "은", "는", "을", "를", "의", "에", "서", "도",
    "로", "으로", "와", "과", "하고", "이나", "나", "에서", "에게",
    "한테", "께", "에게서", "한테서", "처럼", "같이", "보다", "까지",
    "부터", "만", "라도", "이라도", "라고", "이라고", "고", "며",
    "이며", "거나", "이거나", "든지", "이든지", "이고",
})

_TOKEN_PATTERN = re.compile(r"[a-zA-Z\uAC00-\uD7A3]+")


def _tokenize(text: str) -> list[str]:
    """Extract tokens from text using regex, lowercase, filter len <= 2."""
    tokens = _TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if len(t) > 2]


def extract_keywords(texts: list[str], top_n: int = 30) -> list[dict[str, Any]]:
    """Extract top_n keywords from a list of texts, excluding stopwords.

    Args:
        texts: List of text strings to analyze.
        top_n: Number of top keywords to return.

    Returns:
        List of dicts with "word" and "count" keys, sorted by count descending.
    """
    counter: Counter[str] = Counter()
    all_stopwords = ENGLISH_STOPWORDS | KOREAN_STOPWORDS

    for text in texts:
        tokens = _tokenize(text)
        for token in tokens:
            if token not in all_stopwords:
                counter[token] += 1

    return [{"word": word, "count": count} for word, count in counter.most_common(top_n)]


def compute_review_stats(reviews: list[dict[str, Any]], top_n: int = 30) -> dict[str, Any]:
    """Compute review statistics including positive ratio and top keywords.

    Args:
        reviews: List of dicts with "voted_up" (bool) and "review_text" (str).
        top_n: Number of top keywords to return per category.

    Returns:
        Dict with:
            - total_reviews: int
            - positive_ratio: float (0.0 if no reviews)
            - top_keywords_positive: list[dict] with word/count
            - top_keywords_negative: list[dict] with word/count
    """
    if not reviews:
        return {
            "total_reviews": 0,
            "positive_ratio": 0.0,
            "top_keywords_positive": [],
            "top_keywords_negative": [],
        }

    total = len(reviews)
    positive_texts: list[str] = []
    negative_texts: list[str] = []

    for review in reviews:
        text = review.get("review_text", "") or ""
        if review.get("voted_up"):
            positive_texts.append(text)
        else:
            negative_texts.append(text)

    positive_count = len(positive_texts)
    positive_ratio = positive_count / total

    return {
        "total_reviews": total,
        "positive_ratio": positive_ratio,
        "top_keywords_positive": extract_keywords(positive_texts, top_n=top_n),
        "top_keywords_negative": extract_keywords(negative_texts, top_n=top_n),
    }
