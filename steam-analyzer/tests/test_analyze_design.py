"""Tests for handle_analyze_design tool."""

from __future__ import annotations

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call(conn, **kwargs):
    from steam_analyzer.tools.analyze_design import handle_analyze_design
    return handle_analyze_design(conn, **kwargs)


# ---------------------------------------------------------------------------
# Error cases – missing inputs
# ---------------------------------------------------------------------------

class TestMissingInputErrors:
    def test_no_design_content_returns_error(self, seeded_db):
        result = _call(seeded_db, tag="Roguelike")
        assert result["error"] is True
        assert result["error_type"] == "no_data"

    def test_no_competitors_returns_error(self, seeded_db):
        result = _call(seeded_db, design_text="My game design")
        assert result["error"] is True
        assert result["error_type"] == "no_data"

    def test_both_missing_returns_error(self, seeded_db):
        result = _call(seeded_db)
        assert result["error"] is True
        assert result["error_type"] == "no_data"


# ---------------------------------------------------------------------------
# File-related errors
# ---------------------------------------------------------------------------

class TestFileErrors:
    def test_file_not_found_returns_file_error(self, seeded_db):
        result = _call(
            seeded_db,
            design_file="/nonexistent/path/design.txt",
            tag="Roguelike",
        )
        assert result["error"] is True
        assert result["error_type"] == "file_error"

    def test_file_too_large_returns_file_error(self, seeded_db, tmp_path):
        big_file = tmp_path / "big_design.txt"
        big_file.write_bytes(b"X" * (1024 * 1024 + 1))  # 1 MB + 1 byte
        result = _call(
            seeded_db,
            design_file=str(big_file),
            tag="Roguelike",
        )
        assert result["error"] is True
        assert result["error_type"] == "file_error"


# ---------------------------------------------------------------------------
# Successful analyses
# ---------------------------------------------------------------------------

class TestSuccessfulAnalysis:
    def _assert_success_shape(self, result):
        """Assert that the result has the expected success shape."""
        assert "error" not in result or result.get("error") is False
        assert "design_content" in result
        assert "competitor_summary" in result
        assert "sample_reviews_positive" in result
        assert "sample_reviews_negative" in result

        summary = result["competitor_summary"]
        assert "games_count" in summary
        assert "positive_ratio" in summary
        assert "top_keywords_positive" in summary
        assert "top_keywords_negative" in summary

    def test_analyze_with_design_text_and_tag(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="My roguelike game concept",
            tag="Roguelike",
        )
        self._assert_success_shape(result)
        assert result["design_content"] == "My roguelike game concept"
        assert result["competitor_summary"]["games_count"] == 2

    def test_analyze_with_design_file(self, seeded_db, tmp_path):
        design_file = tmp_path / "design.txt"
        design_file.write_text("Design from file content", encoding="utf-8")
        result = _call(
            seeded_db,
            design_file=str(design_file),
            tag="Roguelike",
        )
        self._assert_success_shape(result)
        assert result["design_content"] == "Design from file content"

    def test_analyze_with_appids(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="My game design",
            appids=[1, 2],
        )
        self._assert_success_shape(result)
        assert result["competitor_summary"]["games_count"] == 2

    def test_analyze_single_appid(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="My game design",
            appids=[3],
        )
        self._assert_success_shape(result)
        assert result["competitor_summary"]["games_count"] == 1

    def test_positive_ratio_is_float(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="Design",
            tag="Roguelike",
        )
        ratio = result["competitor_summary"]["positive_ratio"]
        assert isinstance(ratio, float)
        assert 0.0 <= ratio <= 1.0

    def test_sample_reviews_are_lists(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="Design",
            tag="Roguelike",
        )
        assert isinstance(result["sample_reviews_positive"], list)
        assert isinstance(result["sample_reviews_negative"], list)

    def test_sample_reviews_max_10_each(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="Design",
            tag="Roguelike",
        )
        assert len(result["sample_reviews_positive"]) <= 10
        assert len(result["sample_reviews_negative"]) <= 10

    def test_top_keywords_are_lists(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="Design",
            tag="Roguelike",
        )
        summary = result["competitor_summary"]
        assert isinstance(summary["top_keywords_positive"], list)
        assert isinstance(summary["top_keywords_negative"], list)

    def test_file_exactly_1mb_is_allowed(self, seeded_db, tmp_path):
        exact_file = tmp_path / "exact.txt"
        exact_file.write_bytes(b"A" * (1024 * 1024))  # exactly 1 MB
        result = _call(
            seeded_db,
            design_file=str(exact_file),
            tag="Roguelike",
        )
        # Should succeed (no error)
        assert "error" not in result or result.get("error") is not True

    def test_unknown_tag_returns_zero_games(self, seeded_db):
        result = _call(
            seeded_db,
            design_text="Design",
            tag="NonExistentTag",
        )
        # Not an error — just 0 competitors found; implementation may vary,
        # but if it returns success it should have 0 games_count.
        if not result.get("error"):
            assert result["competitor_summary"]["games_count"] == 0
