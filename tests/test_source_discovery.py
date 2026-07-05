from pathlib import Path

import pytest

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


def fake_listing_get(
    html: str,
    status_code: int | None = 200,
    error_message: str | None = None,
):
    def _get(url: str) -> DiscoveryHttpResponse:
        return DiscoveryHttpResponse(
            url=url,
            status_code=status_code,
            text=html,
            error_message=error_message,
        )

    return _get


def source_link(db, home_team="England", away_team="Ghana", source="betexplorer"):
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        home_team,
        away_team,
    )[0]
    links = db.list_fixture_source_links(int(fixture["fixture_id"]))
    return next(link for link in links if link["source"] == source)


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


def test_register_fixture_source_url_accepts_positional_arguments(tmp_path):
    db = seeded_db(tmp_path)

    result = register_fixture_source_url(
        db,
        "England",
        "Ghana",
        "betexplorer",
        "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url.endswith("/england-ghana/KhgvzGjJ/")


def test_register_fixture_source_url_rejects_unsupported_source(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        register_fixture_source_url(
            db,
            home_team="England",
            away_team="Ghana",
            source="unknown",
            url="https://www.betexplorer.com/england-ghana",
        )


def test_register_fixture_source_url_rejects_off_domain_url(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported URL host for betexplorer"):
        register_fixture_source_url(
            db,
            home_team="England",
            away_team="Ghana",
            source="betexplorer",
            url="https://example.invalid/england-ghana",
        )


def test_discover_fixture_source_from_betexplorer_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        "England",
        "Ghana",
        "betexplorer",
        html,
        "https://www.betexplorer.com",
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


def test_discover_fixture_source_from_listing_rejects_unsupported_source(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        discover_fixture_source_from_listing(
            db,
            home_team="England",
            away_team="Ghana",
            source="unknown",
            listing_html="<a href='/england-ghana'>England - Ghana</a>",
            base_url="https://www.betexplorer.com",
        )


def test_discover_fixture_source_from_listing_ignores_off_domain_match(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html=(
            "<html><a href='https://example.invalid/england-ghana'>"
            "England - Ghana</a></html>"
        ),
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.MANUAL_REQUIRED
    assert result.url is None
    persisted = source_link(db)
    assert persisted["status"] == "manual_required"
    assert persisted["url"] is None


def test_discover_fixture_source_from_listing_preserves_available_link_on_match(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/england-ghana.html",
        url="https://www.betexplorer.com/england-ghana",
        status="available",
    )
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html=html,
        base_url="https://www.betexplorer.com",
    )

    persisted = source_link(db)
    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path == "data/cache/betexplorer/england-ghana.html"
    assert result.url == "https://www.betexplorer.com/england-ghana"
    assert persisted["status"] == "available"
    assert persisted["html_path"] == "data/cache/betexplorer/england-ghana.html"
    assert persisted["url"] == "https://www.betexplorer.com/england-ghana"


def test_discover_fixture_source_from_listing_matches_seeded_usa_alias(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source_from_listing(
        db,
        home_team="United States",
        away_team="Paraguay",
        source="betexplorer",
        listing_html="<html><a href='/football/world/world-championship-2026/usa-paraguay/'>USA - Paraguay</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/usa-paraguay/"


def test_discover_fixture_source_from_listing_matches_seeded_ivory_coast_alias(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source_from_listing(
        db,
        home_team="Ivory Coast",
        away_team="Germany",
        source="betexplorer",
        listing_html="<html><a href='/football/world/world-championship-2026/cote-d-ivoire-germany/'>Cote d'Ivoire - Germany</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/cote-d-ivoire-germany/"


def test_discover_fixture_source_fetches_default_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")
    requested_urls = []

    def http_get(url: str) -> DiscoveryHttpResponse:
        requested_urls.append(url)
        return DiscoveryHttpResponse(url=url, status_code=200, text=html)

    result = discover_fixture_source(
        db, "England", "Ghana", "BetExplorer", http_get
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.source == "betexplorer"
    assert requested_urls == [
        "https://www.betexplorer.com/football/world/world-championship-2026/fixtures/"
    ]
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/"


def test_discover_fixture_source_parses_listing_with_login_nav(tmp_path):
    db = seeded_db(tmp_path)
    html = """
    <html>
      <a href="/login">Login</a>
      <a href="/football/world/world-championship-2026/england-ghana/KhgvzGjJ/">England - Ghana</a>
    </html>
    """

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
    persisted = source_link(db)
    assert persisted["status"] == "blocked"
    assert persisted["url"] is None
    assert persisted["html_path"] is None


def test_discover_fixture_source_marks_402_listing_as_blocked(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get("<html>payment required</html>", status_code=402),
    )

    assert result.status is SourceLinkStatus.BLOCKED
    assert result.url is None
    assert result.warnings == ("listing fetch blocked by source",)
    persisted = source_link(db)
    assert persisted["status"] == "blocked"
    assert persisted["url"] is None
    assert persisted["html_path"] is None


def test_discover_fixture_source_marks_login_listing_as_blocked(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get("<html>login required</html>"),
    )

    assert result.status is SourceLinkStatus.BLOCKED
    assert result.url is None
    assert result.warnings == ("listing fetch blocked by source",)
    persisted = source_link(db)
    assert persisted["status"] == "blocked"
    assert persisted["url"] is None
    assert persisted["html_path"] is None


def test_discover_fixture_source_reports_http_error_message_as_failed(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get("", status_code=None, error_message="dns failed"),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert result.url is None
    assert result.warnings == ("dns failed",)
    persisted = source_link(db)
    assert persisted["status"] == "failed"
    assert persisted["url"] is None
    assert persisted["html_path"] is None


def test_discover_fixture_source_rejects_unsupported_source(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        discover_fixture_source(
            db,
            home_team="England",
            away_team="Ghana",
            source="unknown",
            http_get=fake_listing_get(""),
        )


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
    persisted = source_link(db)
    assert persisted["status"] == "manual_required"
    assert persisted["url"] is None
    assert persisted["html_path"] is None


def test_discovery_no_match_preserves_pending_source_link(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/manual.html",
        url="https://www.betexplorer.com/england-ghana",
        status="pending",
    )

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html="<html><a href='/other'>Brazil - Morocco</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.MANUAL_REQUIRED
    assert result.url == "https://www.betexplorer.com/england-ghana"
    assert result.html_path == "data/cache/betexplorer/manual.html"
    persisted = source_link(db)
    assert persisted["status"] == "manual_required"
    assert persisted["url"] == "https://www.betexplorer.com/england-ghana"
    assert persisted["html_path"] == "data/cache/betexplorer/manual.html"


@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        (
            fake_listing_get("<html>captcha required</html>", status_code=403),
            SourceLinkStatus.BLOCKED,
        ),
        (
            fake_listing_get("", status_code=None, error_message="dns failed"),
            SourceLinkStatus.FAILED,
        ),
    ],
)
def test_discovery_listing_failure_preserves_pending_source_link(
    tmp_path,
    response,
    expected_status,
):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/manual.html",
        url="https://www.betexplorer.com/england-ghana",
        status="pending",
    )

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=response,
    )

    assert result.status is expected_status
    assert result.url == "https://www.betexplorer.com/england-ghana"
    assert result.html_path == "data/cache/betexplorer/manual.html"
    persisted = source_link(db)
    assert persisted["status"] == expected_status.value
    assert persisted["url"] == "https://www.betexplorer.com/england-ghana"
    assert persisted["html_path"] == "data/cache/betexplorer/manual.html"


def test_discovery_failure_does_not_overwrite_available_source_link(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/england-ghana.html",
        url="https://www.betexplorer.com/england-ghana",
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
    assert result.url == "https://www.betexplorer.com/england-ghana"
    assert "No source URL found for England vs Ghana" in result.warnings
