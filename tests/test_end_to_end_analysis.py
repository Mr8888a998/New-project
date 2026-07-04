from pathlib import Path

from typer.testing import CliRunner

from handicap_ai.adapters.free_web import FreeWebHtmlAdapter
from handicap_ai.cli import app
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles


def test_analyze_uses_web_fixture_opening_closing_lines(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    db = Database(db_path)
    db.migrate()
    ingest_bundles(
        db,
        FreeWebHtmlAdapter(
            "fixture-web",
            Path("tests/fixtures/free_web_match.html"),
        ).load(),
    )

    result = CliRunner().invoke(
        app,
        ["analyze", "--db", str(db_path), "--home", "England", "--away", "Panama"],
    )

    assert result.exit_code == 0
    assert "Handicap pick: away" in result.output
    assert "Total pick: under" in result.output
    assert "1X2 pick: home" in result.output
