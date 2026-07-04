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
    assert "Skipped files: 0" in result.output
    assert "Imported matches: 1" in result.output


def test_import_history_folder_command_reports_invalid_supported_file(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    history_folder = tmp_path / "history"
    history_folder.mkdir()
    (history_folder / "broken.csv").write_text(
        "not,a,football,data,file\n1,2,3,4\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    runner.invoke(app, ["init-db", "--db", str(db_path)])

    result = runner.invoke(
        app,
        [
            "import-history-folder",
            "--db",
            str(db_path),
            "--path",
            str(history_folder),
            "--season",
            "2026",
        ],
    )

    assert result.exit_code == 0
    assert "Imported files: 0" in result.output
    assert "Skipped files: 1" in result.output
    assert "Imported matches: 0" in result.output
    assert "Import error: broken.csv:" in result.output
