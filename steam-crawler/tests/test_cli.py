from unittest.mock import patch
from click.testing import CliRunner


def test_cli_help():
    from steam_crawler.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "collect" in result.output


def test_collect_help():
    from steam_crawler.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["collect", "--help"])
    assert result.exit_code == 0
    assert "--tag" in result.output
    assert "--genre" in result.output
    assert "--review-type" in result.output


def test_versions_empty(tmp_path):
    from steam_crawler.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["versions", "--db", str(tmp_path / "test.db")])
    assert result.exit_code == 0


def test_status_empty(tmp_path):
    from steam_crawler.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--db", str(tmp_path / "test.db")])
    assert result.exit_code == 0


def test_appids_full_pipeline(tmp_path):
    """--appids를 --step 없이 사용하면 전체 파이프라인이 실행되어야 한다."""
    from steam_crawler.cli import main

    runner = CliRunner()
    db_path = str(tmp_path / "test.db")

    with patch("steam_crawler.pipeline.runner.run_pipeline") as mock_pipeline:
        result = runner.invoke(main, [
            "collect", "--appids", "526870", "--db", db_path
        ])
        assert result.exit_code == 0, f"Failed: {result.output}"
        mock_pipeline.assert_called_once()
        # step should be None for full pipeline
        call_kwargs = mock_pipeline.call_args
        assert call_kwargs[1].get("step") is None


def test_appids_with_step1(tmp_path):
    """--appids --step 1 조합이 허용되어야 한다."""
    from steam_crawler.cli import main

    runner = CliRunner()
    db_path = str(tmp_path / "test.db")

    with patch("steam_crawler.pipeline.runner.run_pipeline") as mock_pipeline:
        result = runner.invoke(main, [
            "collect", "--appids", "526870", "--step", "1", "--db", db_path
        ])
        assert result.exit_code == 0, f"Failed: {result.output}"
