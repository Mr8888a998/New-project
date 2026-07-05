from pathlib import Path

from typer.testing import CliRunner

from handicap_ai.cli import app


def seed_db(runner: CliRunner, db_path: Path):
    result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])
    assert result.exit_code == 0


def register_source(
    runner: CliRunner,
    db_path: Path,
    home: str = "England",
    away: str = "Panama",
):
    result = runner.invoke(
        app,
        [
            "register-source-url",
            "--db",
            str(db_path),
            "--home",
            home,
            "--away",
            away,
            "--source",
            "betexplorer",
            "--url",
            f"https://www.betexplorer.com/{home.lower()}-{away.lower()}",
        ],
    )
    assert result.exit_code == 0


def assert_no_traceback(output: str):
    assert "Traceback" not in output


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
            "https://www.betexplorer.com/england-ghana",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: pending" in result.output
    assert "url=https://www.betexplorer.com/england-ghana" in result.output


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
            "https://www.betexplorer.com/england-panama",
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


def test_fetch_source_html_command_defaults_to_data_cache(tmp_path, monkeypatch):
    db_path = tmp_path / "handicap.sqlite"
    fixture_path = Path("tests/fixtures/betexplorer_match.html").resolve()
    runner = CliRunner()
    seed_db(runner, db_path)
    register_source(runner, db_path)
    monkeypatch.chdir(tmp_path)

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
            "--response-html",
            str(fixture_path),
        ],
    )

    assert result.exit_code == 0
    assert "html=" in result.output
    assert "data" in result.output
    assert "cache" in result.output
    assert "source-cache" not in result.output


def test_discover_sources_command_reports_missing_listing_html(tmp_path):
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
            str(tmp_path / "missing.html"),
            "--base-url",
            "https://www.betexplorer.com",
        ],
    )

    assert result.exit_code != 0
    assert "cannot read listing HTML" in result.output
    assert_no_traceback(result.output)


def test_fetch_source_html_command_reports_missing_response_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)
    register_source(runner, db_path)

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
            "--response-html",
            str(tmp_path / "missing.html"),
        ],
    )

    assert result.exit_code != 0
    assert "cannot read response HTML" in result.output
    assert_no_traceback(result.output)


def test_fetch_source_html_command_reports_missing_registered_url(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)

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
            "--response-html",
            "tests/fixtures/betexplorer_match.html",
        ],
    )

    assert result.exit_code != 0
    assert "no registered URL" in result.output
    assert_no_traceback(result.output)
