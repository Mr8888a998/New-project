from pathlib import Path

from handicap_ai.cache_scan import scan_cache_html
from handicap_ai.database import Database
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026, import_world_cup_2026_seed


def _fixture_id(db: Database, home: str, away: str) -> int:
    fixture = db.find_tournament_fixtures(FIFA_WORLD_CUP, SEASON_2026, home, away)[0]
    return int(fixture["fixture_id"])


def test_scan_cache_html_reports_parseable_orphan_and_missing_links(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    cache_dir = tmp_path / "cache"
    linked_html = cache_dir / "betexplorer" / "england-panama.html"
    linked_html.parent.mkdir(parents=True)
    linked_html.write_text(
        Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    orphan_html = cache_dir / "oddsportal" / "orphan.html"
    orphan_html.parent.mkdir(parents=True)
    orphan_html.write_text("<html>not a match page</html>", encoding="utf-8")
    missing_html = cache_dir / "betexplorer" / "missing.html"
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "England", "Panama"),
        source="betexplorer",
        html_path=str(linked_html),
        url="https://www.betexplorer.com/example/",
        status="available",
    )
    db.upsert_fixture_source_link(
        fixture_id=_fixture_id(db, "England", "Ghana"),
        source="betexplorer",
        html_path=str(missing_html),
        url="https://www.betexplorer.com/missing/",
        status="available",
    )

    report = scan_cache_html(db, cache_dir=cache_dir)

    assert report.total_files == 2
    assert report.linked_files == 1
    assert report.orphan_files == 1
    assert report.parseable_files == 1
    assert report.invalid_files == 1
    assert report.missing_linked_files == 1
    assert report.files[0].path == str(linked_html)
    assert report.files[0].status == "linked"
    assert report.files[0].parseable is True
    assert report.files[1].status == "invalid"
    assert report.missing_links[0].html_path == str(missing_html)


def test_scan_cache_html_limits_file_rows_without_changing_totals(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    cache_dir = tmp_path / "cache"
    for index in range(3):
        html_path = cache_dir / "betexplorer" / f"bad-{index}.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text("<html>bad</html>", encoding="utf-8")

    report = scan_cache_html(db, cache_dir=cache_dir, limit=2)

    assert report.total_files == 3
    assert report.invalid_files == 3
    assert len(report.files) == 2
