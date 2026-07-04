from typer.testing import CliRunner

from handicap_ai.cli import app


def test_scrape_match_from_saved_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["init-db", "--db", str(db_path)])

    result = runner.invoke(
        app,
        [
            "scrape-match",
            "--db",
            str(db_path),
            "--source",
            "betexplorer",
            "--html",
            "tests/fixtures/betexplorer_match.html",
        ],
    )

    assert result.exit_code == 0
    assert "Scraped England vs Panama from betexplorer" in result.output
    assert "Handicap pick:" in result.output
    assert "Source coverage: complete" in result.output


def test_import_history_folder_command(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["init-db", "--db", str(db_path)])

    result = runner.invoke(
        app,
        [
            "import-history-folder",
            "--db",
            str(db_path),
            "--path",
            "tests/fixtures/history_folder",
            "--season",
            "2026",
        ],
    )

    assert result.exit_code == 0
    assert "Imported files: 1" in result.output
    assert "Imported matches: 1" in result.output
