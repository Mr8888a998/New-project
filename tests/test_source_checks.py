from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_checks import build_source_checks
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026, import_world_cup_2026_seed


def _fixture_id(db: Database, home: str, away: str) -> int:
    fixture = db.find_tournament_fixtures(FIFA_WORLD_CUP, SEASON_2026, home, away)[0]
    return int(fixture["fixture_id"])


def test_build_source_checks_classifies_next_actions(tmp_path):
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
        url="https://www.betexplorer.com/england-ghana/",
        status="pending",
    )
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "Portugal", "Uzbekistan"),
        source="oddsportal",
        html_path=str(tmp_path / "missing.html"),
        url="https://www.oddsportal.com/example/",
        status="available",
    )
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "Colombia", "DR Congo"),
        source="oddsportal",
        html_path=None,
        url="https://www.oddsportal.com/blocked/",
        status="blocked",
    )

    report = build_source_checks(db, sources=("betexplorer", "oddsportal"))

    assert report.total_fixtures == 72
    assert report.total_checks == 144
    assert report.by_action["ready"] == 1
    assert report.by_action["needs_fetch"] == 1
    assert report.by_action["missing_html"] == 1
    assert report.by_action["blocked"] == 1
    assert report.by_action["needs_url"] == 140
    england_ghana = next(
        check
        for check in report.checks
        if check.home_team == "England"
        and check.away_team == "Ghana"
        and check.source == "betexplorer"
    )
    assert england_ghana.action == "needs_fetch"
    assert "Fetch" in england_ghana.reason


def test_build_source_checks_can_filter_and_limit_actions(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "England", "Ghana"),
        source="betexplorer",
        html_path=None,
        url="https://www.betexplorer.com/england-ghana/",
        status="pending",
    )

    report = build_source_checks(
        db,
        sources=("betexplorer", "oddsportal"),
        action="needs_fetch",
        limit=1,
    )

    assert report.total_checks == 144
    assert len(report.checks) == 1
    assert report.checks[0].action == "needs_fetch"
    assert report.checks[0].home_team == "England"
