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
