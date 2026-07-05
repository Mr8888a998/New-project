from pathlib import Path

from typer.testing import CliRunner

from handicap_ai.cli import app


def seed_db(runner: CliRunner, db_path: Path):
    result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])
    assert result.exit_code == 0


def test_register_source_url_command(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)

    result = runner.invoke(
        app,
        [
            "register-source-url",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
            "--source",
            "betexplorer",
            "--url",
            "https://example.test/england-ghana",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: pending" in result.output
    assert "url=https://example.test/england-ghana" in result.output


def test_discover_sources_command_uses_listing_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)

    result = runner.invoke(
        app,
        [
            "discover-sources",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
            "--source",
            "betexplorer",
            "--listing-html",
            "tests/fixtures/source_listing_betexplorer.html",
            "--base-url",
            "https://www.betexplorer.com",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: pending" in result.output
    assert "england-ghana/KhgvzGjJ/" in result.output


def test_fetch_source_html_command_uses_local_response_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    cache_dir = tmp_path / "cache"
    runner = CliRunner()
    seed_db(runner, db_path)
    register = runner.invoke(
        app,
        [
            "register-source-url",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Panama",
            "--source",
            "betexplorer",
            "--url",
            "https://example.test/england-panama",
        ],
    )
    assert register.exit_code == 0

    result = runner.invoke(
        app,
        [
            "fetch-source-html",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Panama",
            "--source",
            "betexplorer",
            "--cache-dir",
            str(cache_dir),
            "--response-html",
            "tests/fixtures/betexplorer_match.html",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: available" in result.output
    assert "html=" in result.output
