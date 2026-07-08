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


def test_backtest_command_prints_market_summary(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
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

    result = runner.invoke(app, ["backtest", "--db", str(db_path), "--limit", "2"])

    assert result.exit_code == 0
    assert "Backtest" in result.output
    assert "handicap" in result.output
    assert "total" in result.output
    assert "1x2" in result.output


def test_source_status_command_prints_readiness(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path)])
    assert seed_result.exit_code == 0

    result = runner.invoke(
        app,
        ["source-status", "--db", str(db_path), "--source", "betexplorer"],
    )

    assert result.exit_code == 0
    assert "Source status" in result.output
    assert "betexplorer" in result.output
    assert "pending" in result.output


def test_source_matrix_command_prints_two_source_summary(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path)])
    assert seed_result.exit_code == 0

    result = runner.invoke(app, ["source-matrix", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Source matrix: fixtures=72 cells=144" in result.output
    assert "betexplorer:" in result.output
    assert "oddsportal:" in result.output
    assert "pending=72" in result.output


def test_source_checks_command_prints_batch_candidate_summary(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path)])
    assert seed_result.exit_code == 0

    result = runner.invoke(app, ["source-checks", "--db", str(db_path), "--limit", "3"])

    assert result.exit_code == 0
    assert "Source checks: fixtures=72 checks=144" in result.output
    assert "needs_url=144" in result.output
    assert "betexplorer needs_url" in result.output


def test_prepare_demo_data_command_seeds_usable_local_data(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["prepare-demo-data", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Prepared demo data" in result.output
    assert "fixtures=72" in result.output
    assert "available_html=1" in result.output
    assert "finished_matches=" in result.output
