from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_matrix import build_source_matrix
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026, import_world_cup_2026_seed


def _fixture_id(db: Database, home: str, away: str) -> int:
    fixture = db.find_tournament_fixtures(FIFA_WORLD_CUP, SEASON_2026, home, away)[0]
    return int(fixture["fixture_id"])


def test_build_source_matrix_summarizes_two_sources(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    html_path = tmp_path / "england-panama.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "England", "Panama"),
        source="betexplorer",
        html_path=str(html_path),
        url="https://www.betexplorer.com/example/",
        status="available",
    )
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "England", "Ghana"),
        source="betexplorer",
        html_path=None,
        url="https://www.betexplorer.com/blocked/",
        status="blocked",
    )
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "Portugal", "Uzbekistan"),
        source="oddsportal",
        html_path=str(tmp_path / "missing.html"),
        url="https://www.oddsportal.com/example/",
        status="available",
    )

    matrix = build_source_matrix(db, sources=("betexplorer", "oddsportal"))

    assert matrix.total_fixtures == 72
    assert matrix.total_source_cells == 144
    assert matrix.sources["betexplorer"].by_status["available"] == 1
    assert matrix.sources["betexplorer"].by_status["blocked"] == 1
    assert matrix.sources["betexplorer"].by_status["pending"] == 70
    assert matrix.sources["betexplorer"].available_html == 1
    assert matrix.sources["betexplorer"].registered_urls == 2
    assert matrix.sources["oddsportal"].by_status["missing_html"] == 1
    assert matrix.sources["oddsportal"].by_status["pending"] == 71


def test_source_matrix_fixture_rows_include_per_source_state(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)

    matrix = build_source_matrix(db, sources=("betexplorer", "oddsportal"))
    england_panama = next(
        fixture
        for fixture in matrix.fixtures
        if fixture.home_team == "England" and fixture.away_team == "Panama"
    )

    assert england_panama.sources["betexplorer"].status == "pending"
    assert england_panama.sources["oddsportal"].status == "pending"
    assert matrix.to_dict()["sources"]["betexplorer"]["total"] == 72
