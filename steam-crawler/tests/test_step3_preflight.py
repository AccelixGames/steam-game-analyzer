"""Tests for step3 appids filter and preflight log."""
from io import StringIO
from unittest.mock import patch

import pytest

from steam_crawler.db.schema import init_db
from steam_crawler.db.repository import upsert_game
from steam_crawler.models.game import GameSummary

from rich.console import Console


@pytest.fixture
def db_with_games(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    # version=0 must exist in data_versions for FK constraints in game_collection_status
    conn.execute("INSERT INTO data_versions (version, query_type, status) VALUES (0, 'test', 'running')")
    conn.commit()
    for appid, name, pos in [(100, "GameA", 500), (200, "GameB", 300), (300, "GameC", 100)]:
        upsert_game(conn, GameSummary(appid=appid, name=name, positive=pos, negative=10), version=0)
    yield conn
    conn.close()


@pytest.fixture
def capture_console():
    """Patch step3's console with a capturing Console to reliably capture Rich output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, no_color=True)
    with patch("steam_crawler.pipeline.step3_crawl.console", test_console):
        yield buf


def test_step3_appids_filters_games(db_with_games, capture_console):
    """run_step3 with appids should only process those games."""
    from steam_crawler.pipeline.step3_crawl import run_step3

    run_step3(db_with_games, version=0, appids=[200], max_reviews=0)

    output = capture_console.getvalue()
    assert "GameB" in output
    assert "GameA" not in output
    assert "GameC" not in output


def test_step3_preflight_log_content(db_with_games, capture_console):
    """Preflight log should list game names, appids, and count."""
    from steam_crawler.pipeline.step3_crawl import run_step3

    run_step3(db_with_games, version=0, appids=[100, 300], max_reviews=0)

    output = capture_console.getvalue()
    assert "[Preflight]" in output
    assert "GameA" in output
    assert "GameC" in output
    assert "2 game(s)" in output


def test_step3_no_appids_uses_top_n(db_with_games, capture_console):
    """Without appids, should use top_n limit (backward compat)."""
    from steam_crawler.pipeline.step3_crawl import run_step3

    run_step3(db_with_games, version=0, top_n=2, max_reviews=0)

    output = capture_console.getvalue()
    assert "GameA" in output
    assert "GameB" in output
    assert "2 game(s)" in output


def test_step3_empty_appids_returns_zero(db_with_games, capture_console):
    """Empty appids list should return 0 without crashing."""
    from steam_crawler.pipeline.step3_crawl import run_step3

    result = run_step3(db_with_games, version=0, appids=[], max_reviews=0)

    assert result == 0
    output = capture_console.getvalue()
    assert "0 game(s)" in output
