from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.manual_html import save_manual_fixture_html
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026, import_world_cup_2026_seed


def _fixture_id(db: Database, home: str, away: str) -> int:
    fixture = db.find_tournament_fixtures(FIFA_WORLD_CUP, SEASON_2026, home, away)[0]
    return int(fixture["fixture_id"])


def _source_link(db: Database, fixture_id: int, source: str):
    return next(link for link in db.list_fixture_source_links(fixture_id) if link["source"] == source)


def test_save_manual_fixture_html_caches_and_registers_without_url(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    result = save_manual_fixture_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        html=html,
        cache_dir=tmp_path / "cache",
    )

    assert result.status.value == "available"
    assert result.url is None
    assert result.html_path is not None
    assert Path(result.html_path).is_file()
    link = _source_link(db, _fixture_id(db, "England", "Panama"), "betexplorer")
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path
    assert link["url"] is None
    fetches = db.list_source_fetches("betexplorer")
    assert fetches[0]["url"].startswith("manual://fixture/")
    assert fetches[0]["cache_path"] == result.html_path


def test_save_manual_fixture_html_rejects_wrong_fixture(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    result = save_manual_fixture_html(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        html=html,
        cache_dir=tmp_path / "cache",
    )

    assert result.status.value == "failed"
    assert result.html_path is None
    assert "does not match England vs Ghana" in result.warnings[0]
    assert not db.list_fixture_source_links(_fixture_id(db, "England", "Ghana"))
