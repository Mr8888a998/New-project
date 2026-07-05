from pathlib import Path

import pytest

from handicap_ai.database import Database
from handicap_ai.source_discovery import SourceLinkStatus, register_fixture_source_url
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    register_fixture_source_url(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        url="https://example.test/england-panama",
    )
    return db


def seeded_db_without_source(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def fake_get(
    html: str,
    status_code: int | None = 200,
    error_message: str | None = None,
):
    def _get(url: str) -> FetchHttpResponse:
        return FetchHttpResponse(
            url=url,
            status_code=status_code,
            text=html,
            error_message=error_message,
        )

    return _get


def source_link(
    db,
    source="betexplorer",
    home_team="England",
    away_team="Panama",
):
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        home_team,
        away_team,
    )[0]
    links = db.list_fixture_source_links(int(fixture["fixture_id"]))
    return next(link for link in links if link["source"] == source.lower())


def test_fetch_fixture_source_html_caches_available_html(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path is not None
    assert Path(result.html_path).is_file()
    assert db.list_source_fetches("betexplorer")[0]["status_code"] == 200
    link = source_link(db)
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path


def test_fetch_fixture_source_html_caches_oddsportal_html(tmp_path):
    db = seeded_db(tmp_path)
    register_fixture_source_url(
        db,
        home_team="England",
        away_team="Panama",
        source="OddsPortal",
        url="https://example.test/england-panama-oddsportal",
    )
    html = Path("tests/fixtures/oddsportal_match.html").read_text(encoding="utf-8")

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="OddsPortal",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path is not None
    assert Path(result.html_path).is_file()
    assert db.list_source_fetches("oddsportal")[0]["status_code"] == 200
    link = source_link(db, "oddsportal")
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path


def test_fetch_fixture_source_html_accepts_seeded_usa_alias(tmp_path):
    db = seeded_db_without_source(tmp_path)
    register_fixture_source_url(
        db,
        home_team="United States",
        away_team="Paraguay",
        source="betexplorer",
        url="https://example.test/usa-paraguay",
    )
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    html = html.replace("England - Panama", "USA - Paraguay")
    html = html.replace("be:england-panama", "be:usa-paraguay")

    result = fetch_fixture_source_html(
        db,
        home_team="United States",
        away_team="Paraguay",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    link = source_link(db, "betexplorer", "United States", "Paraguay")
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path


def test_fetch_fixture_source_html_accepts_seeded_ivory_coast_alias(tmp_path):
    db = seeded_db_without_source(tmp_path)
    register_fixture_source_url(
        db,
        home_team="Ivory Coast",
        away_team="Germany",
        source="betexplorer",
        url="https://example.test/cote-divoire-germany",
    )
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    html = html.replace("England - Panama", "Cote d'Ivoire - Germany")
    html = html.replace("be:england-panama", "be:cote-d-ivoire-germany")

    result = fetch_fixture_source_html(
        db,
        home_team="Ivory Coast",
        away_team="Germany",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    link = source_link(db, "betexplorer", "Ivory Coast", "Germany")
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path


def test_fetch_fixture_source_html_accepts_valid_page_with_login_nav(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    html = html.replace("<body>", '<body><a href="/login">Login</a>', 1)

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE


def test_fetch_fixture_source_html_marks_blocked_without_overwriting_available(tmp_path):
    db = seeded_db(tmp_path)
    good_html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    first = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(good_html),
    )

    blocked = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("<html>captcha required</html>", status_code=403),
    )

    assert blocked.status is SourceLinkStatus.BLOCKED
    link = source_link(db)
    assert link["status"] == "available"
    assert link["html_path"] == first.html_path


def test_fetch_fixture_source_html_rejects_malformed_html(tmp_path):
    db = seeded_db(tmp_path)

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("<html>not a match page</html>"),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert result.html_path is None
    assert "missing BetExplorer match container" in result.warnings[0]
    fetch = db.list_source_fetches("betexplorer")[0]
    assert "missing BetExplorer match container" in fetch["error_message"]
    assert fetch["cache_path"] is not None
    assert Path(fetch["cache_path"]).is_file()
    link = source_link(db)
    assert link["status"] != "available"
    assert link["html_path"] is None


def test_fetch_fixture_source_html_rejects_incomplete_markets(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_missing_market.html").read_text(
        encoding="utf-8"
    )

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert result.html_path is None
    assert "missing markets" in result.warnings[0]
    assert "totals" in result.warnings[0]
    fetch = db.list_source_fetches("betexplorer")[0]
    assert "missing markets" in fetch["error_message"]
    assert "totals" in fetch["error_message"]
    assert fetch["cache_path"] is not None
    assert Path(fetch["cache_path"]).is_file()
    assert source_link(db)["status"] != "available"


def test_fetch_fixture_source_html_rejects_wrong_fixture_page(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    html = html.replace("England - Panama", "Brazil - Morocco")
    html = html.replace("be:england-panama", "be:brazil-morocco")

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert result.html_path is None
    assert "fetched match Brazil vs Morocco does not match England vs Panama" in (
        result.warnings[0]
    )
    fetch = db.list_source_fetches("betexplorer")[0]
    assert "does not match England vs Panama" in fetch["error_message"]
    link = source_link(db)
    assert link["status"] != "available"
    assert link["html_path"] is None


def test_fetch_fixture_source_html_failed_retry_returns_previous_available_path(
    tmp_path,
):
    db = seeded_db(tmp_path)
    good_html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    first = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(good_html),
    )

    retry = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("<html>not a match page</html>"),
    )

    assert retry.status is SourceLinkStatus.FAILED
    assert retry.html_path == first.html_path
    link = source_link(db)
    assert link["status"] == "available"
    assert link["html_path"] == first.html_path


def test_fetch_fixture_source_html_records_transport_error(tmp_path):
    db = seeded_db(tmp_path)

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("", status_code=None, error_message="dns failed"),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert result.html_path is None
    assert result.warnings == ("dns failed",)
    fetch = db.list_source_fetches("betexplorer")[0]
    assert fetch["status_code"] is None
    assert fetch["cache_path"] is None
    assert fetch["error_message"] == "dns failed"


def test_fetch_fixture_source_html_requires_registered_url(tmp_path):
    db = seeded_db_without_source(tmp_path)

    with pytest.raises(
        ValueError,
        match="no registered URL for betexplorer England vs Panama",
    ):
        fetch_fixture_source_html(
            db,
            home_team="England",
            away_team="Panama",
            source="betexplorer",
            cache_dir=tmp_path / "cache",
            http_get=fake_get(""),
        )


def test_fetch_fixture_source_html_rejects_unsupported_source_before_http_get(tmp_path):
    db = seeded_db_without_source(tmp_path)
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="unknown",
        html_path=None,
        url="https://example.test/england-panama",
        status="pending",
    )
    requested_urls = []

    def http_get(url: str) -> FetchHttpResponse:
        requested_urls.append(url)
        return FetchHttpResponse(url=url, status_code=200, text="<html></html>")

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        fetch_fixture_source_html(
            db,
            home_team="England",
            away_team="Panama",
            source="unknown",
            cache_dir=tmp_path / "cache",
            http_get=http_get,
        )

    assert requested_urls == []


def test_fetch_fixture_source_html_rejects_off_domain_url_before_http_get(tmp_path):
    db = seeded_db_without_source(tmp_path)
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path=None,
        url="https://example.invalid/england-panama",
        status="pending",
    )
    requested_urls = []

    def http_get(url: str) -> FetchHttpResponse:
        requested_urls.append(url)
        return FetchHttpResponse(url=url, status_code=200, text="<html></html>")

    with pytest.raises(ValueError, match="unsupported URL host for betexplorer"):
        fetch_fixture_source_html(
            db,
            home_team="England",
            away_team="Panama",
            source="betexplorer",
            cache_dir=tmp_path / "cache",
            http_get=http_get,
        )

    assert requested_urls == []
