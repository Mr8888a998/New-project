from typer.testing import CliRunner

from handicap_ai.cli import app


def test_seed_world_cup_command_imports_seed(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    result = CliRunner().invoke(
        app,
        [
            "seed-world-cup",
            "--db",
            str(db_path),
            "--season",
            "2026",
        ],
    )

    assert result.exit_code == 0
    assert "World Cup teams: 48" in result.output
    assert "World Cup fixtures: 72" in result.output


def test_find_candidates_command_prints_fixture(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])

    result = runner.invoke(
        app,
        [
            "find-candidates",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
        ],
    )

    assert result.exit_code == 0
    assert "Status: needs_html" in result.output
    assert "Group L: England vs Ghana" in result.output


def test_find_candidates_command_prints_invalid_team(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])

    result = runner.invoke(
        app,
        [
            "find-candidates",
            "--db",
            str(db_path),
            "--home",
            "Atlantis",
            "--away",
            "Ghana",
        ],
    )

    assert result.exit_code == 0
    assert "Status: invalid_team" in result.output
    assert "Unknown team: Atlantis" in result.output
