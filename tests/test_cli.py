from typer.testing import CliRunner

from handicap_ai.cli import app


def test_cli_import_and_analyze(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()

    init_result = runner.invoke(app, ["init-db", "--db", str(db_path)])
    assert init_result.exit_code == 0

    import_result = runner.invoke(
        app,
        [
            "import-football-data",
            "--db",
            str(db_path),
            "--csv",
            "tests/fixtures/football_data_sample.csv",
            "--season",
            "2026",
        ],
    )
    assert import_result.exit_code == 0
    assert "Imported 2 matches" in import_result.output

    analyze_result = runner.invoke(
        app,
        ["analyze", "--db", str(db_path), "--home", "England", "--away", "Panama"],
    )
    assert analyze_result.exit_code == 0
    assert "Handicap pick:" in analyze_result.output
    assert "Total pick:" in analyze_result.output
    assert "1X2 pick:" in analyze_result.output
