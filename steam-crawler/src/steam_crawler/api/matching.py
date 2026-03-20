"""Game name matching utilities for cross-source ID resolution."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


class GameMatcher:
    """Matches games across sources using name similarity."""

    SIMILARITY_THRESHOLD = 0.8

    def name_similarity(self, a: str, b: str) -> float:
        """Compute similarity ratio between two game names (case-insensitive)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def best_match(
        self, name: str, candidates: list[dict[str, Any]], name_key: str = "name"
    ) -> dict[str, Any] | None:
        """Find the best matching candidate above SIMILARITY_THRESHOLD.
        Returns the candidate dict or None."""
        if not candidates:
            return None

        best = None
        best_score = 0.0

        for candidate in candidates:
            score = self.name_similarity(name, candidate[name_key])
            if score > best_score:
                best_score = score
                best = candidate

        if best_score >= self.SIMILARITY_THRESHOLD:
            return best
        return None
