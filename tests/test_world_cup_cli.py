from typer.testing import CliRunner

from handicap_ai.cli import app
from handicap_ai.database import Database
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP


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
    assert "World Cup aliases: 9" in result.output


def test_seed_world_cup_command_rejects_unsupported_season(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    result = CliRunner().invoke(
        app,
        [
            "seed-world-cup",
            "--db",
            str(db_path),
            "--season",
            "2030",
        ],
    )

    assert result.exit_code != 0
    assert "only 2026 is supported in this seed" in result.output


def test_find_candidates_command_prints_fixture(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(
        app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"]
    )
    assert seed_result.exit_code == 0

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


def test_find_candidates_command_prints_source_link_url(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(
        app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"]
    )
    assert seed_result.exit_code == 0

    database = Database(db_path)
    fixture = database.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        "2026",
        "England",
        "Panama",
    )[0]
    database.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        status="pending",
        html_path=None,
        url="https://www.betexplorer.com/england-panama",
    )

    result = runner.invoke(
        app,
        [
            "find-candidates",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Panama",
        ],
    )

    assert result.exit_code == 0
    assert "- betexplorer: pending" in result.output
    assert "url=https://www.betexplorer.com/england-panama" in result.output


def test_find_candidates_command_prints_invalid_team(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_result = runner.invoke(
        app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"]
    )
    assert seed_result.exit_code == 0

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
