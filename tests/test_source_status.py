from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_status import summarize_world_cup_sources
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def test_summarize_world_cup_sources_counts_fixture_readiness(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)

    summary = summarize_world_cup_sources(db, source="betexplorer")

    assert summary.total_fixtures == 72
    assert summary.by_status["pending"] == 72
    assert summary.available_html == 0
    assert summary.to_dict()["source"] == "betexplorer"


def test_summarize_world_cup_sources_counts_existing_available_html(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    html_path = tmp_path / "england-ghana.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Ghana",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path=str(html_path),
        url="https://www.betexplorer.com/example/",
        status="available",
    )

    summary = summarize_world_cup_sources(db, source="betexplorer")

    assert summary.by_status["available"] == 1
    assert summary.available_html == 1
    assert any(
        fixture.html_path and Path(fixture.html_path).is_file()
        for fixture in summary.fixtures
    )
