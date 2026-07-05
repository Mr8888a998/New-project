from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_discovery import (
    DiscoveryHttpResponse,
    SourceLinkStatus,
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def fake_listing_get(html: str, status_code: int = 200):
    def _get(url: str) -> DiscoveryHttpResponse:
        return DiscoveryHttpResponse(url=url, status_code=status_code, text=html)

    return _get


def test_register_fixture_source_url_updates_candidate_link(tmp_path):
    db = seeded_db(tmp_path)

    result = register_fixture_source_url(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        url="https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url.endswith("/england-ghana/KhgvzGjJ/")
    fixtures = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")
    links = db.list_fixture_source_links(int(fixtures[0]["fixture_id"]))
    assert links[0]["source"] == "betexplorer"
    assert links[0]["status"] == "pending"
    assert links[0]["url"] == result.url
    assert links[0]["html_path"] is None


def test_discover_fixture_source_from_betexplorer_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html=html,
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/"


def test_discover_fixture_source_from_oddsportal_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_oddsportal.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="oddsportal",
        listing_html=html,
        base_url="https://www.oddsportal.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.oddsportal.com/football/world/world-championship-2026/england-ghana/"


def test_discover_fixture_source_fetches_default_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get(html),
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/"


def test_discover_fixture_source_marks_blocked_when_listing_blocked(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get("<html>captcha required</html>", status_code=403),
    )

    assert result.status is SourceLinkStatus.BLOCKED
    assert result.url is None
    assert "blocked" in result.warnings[0]


def test_discovery_reports_manual_required_when_no_listing_match(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html="<html><a href='/other'>Brazil - Morocco</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.MANUAL_REQUIRED
    assert result.url is None
    assert "No source URL found for England vs Ghana" in result.warnings


def test_discovery_failure_does_not_overwrite_available_source_link(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/england-ghana.html",
        url="https://example.test/england-ghana",
        status="available",
    )

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html="<html><a href='/other'>Brazil - Morocco</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path == "data/cache/betexplorer/england-ghana.html"
    assert result.url == "https://example.test/england-ghana"
    assert "No source URL found for England vs Ghana" in result.warnings
