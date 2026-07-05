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


def source_link(db, source="betexplorer"):
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]
    links = db.list_fixture_source_links(int(fixture["fixture_id"]))
    return next(link for link in links if link["source"] == source)


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
