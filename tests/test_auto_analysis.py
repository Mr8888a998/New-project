from pathlib import Path

import pytest

import handicap_ai.auto_analysis as auto_analysis
from handicap_ai.auto_analysis import AutoAnalyzeStatus, auto_analyze_candidate
from handicap_ai.database import Database
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def england_panama_fixture(db):
    return db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]


def fail_network_runner(*args, **kwargs):
    raise AssertionError("candidate status mapping must not discover or fetch")


def test_auto_analyze_maps_unknown_home_team_to_invalid_team(tmp_path):
    db = seeded_db(tmp_path)

    result = auto_analyze_candidate(
        db,
        home_team="Unknownland",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=fail_network_runner,
        fetch_runner=fail_network_runner,
    )

    assert result.status is AutoAnalyzeStatus.INVALID_TEAM
    assert result.stage == "candidate_checked"
    assert "Unknown team: Unknownland" in result.warnings
    assert result.candidate is None
    assert result.source_link is None
    assert result.analysis is None


def test_auto_analyze_maps_seeded_teams_without_fixture_to_not_in_group_stage(
    tmp_path,
):
    db = seeded_db(tmp_path)

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="France",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=fail_network_runner,
        fetch_runner=fail_network_runner,
    )

    assert result.status is AutoAnalyzeStatus.NOT_IN_GROUP_STAGE
    assert result.stage == "candidate_checked"
    assert result.warnings == (
        "Both teams are seeded, but no group-stage fixture was found",
    )
    assert result.candidate is None
    assert result.source_link is None
    assert result.analysis is None


def test_auto_analyze_uses_cached_available_html_without_network(tmp_path):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )

    def discovery_runner(*args, **kwargs):
        raise AssertionError("cached auto-analysis must not discover")

    def fetch_runner(*args, **kwargs):
        raise AssertionError("cached auto-analysis must not fetch")

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.ANALYSIS_READY
    assert result.stage == "analyzed"
    assert result.analysis is not None
    assert result.source_link is not None
    assert result.source_link.html_path == "tests/fixtures/betexplorer_match.html"
    assert result.candidate is not None
    assert result.candidate.home_team == "England"
    assert result.candidate.away_team == "Panama"
    assert result.warnings == ()


def test_auto_analyze_discovers_fetches_and_analyzes_html(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    calls = []

    def discovery_runner(db, home_team, away_team, source):
        calls.append("discover")
        return register_fixture_source_url(
            db,
            home_team,
            away_team,
            source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        calls.append("fetch")

        def http_get(url):
            return FetchHttpResponse(url=url, status_code=200, text=html)

        return fetch_fixture_source_html(
            db,
            home_team,
            away_team,
            source,
            cache_dir=cache_dir,
            http_get=http_get,
        )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert calls == ["discover", "fetch"]
    assert result.status is AutoAnalyzeStatus.ANALYSIS_READY
    assert result.stage == "analyzed"
    assert result.source_link is not None
    assert result.source_link.status is SourceLinkStatus.AVAILABLE
    assert result.source_link.html_path is not None
    assert Path(result.source_link.html_path).is_file()
    assert result.analysis is not None


def test_auto_analyze_returns_manual_source_when_discovery_has_no_url(tmp_path):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)

    def discovery_runner(db, home_team, away_team, source):
        return SourceLinkResult(
            status=SourceLinkStatus.MANUAL_REQUIRED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url=None,
            warnings=("No source URL found for England vs Panama",),
        )

    def fetch_runner(*args, **kwargs):
        raise AssertionError("manual source result must not fetch")

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE
    assert result.stage == "manual_required"
    assert result.analysis is None
    assert "No source URL found" in result.warnings[0]


def test_auto_analyze_fetches_when_discovered_html_is_missing(tmp_path):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)
    missing_html_path = tmp_path / "missing-file.html"
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    calls = []
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path=str(missing_html_path),
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )

    def discovery_runner(db, home_team, away_team, source):
        calls.append("discover")
        return SourceLinkResult(
            status=SourceLinkStatus.AVAILABLE,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=str(missing_html_path),
            url="https://www.betexplorer.com/england-panama",
            warnings=("cached HTML missing",),
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        calls.append("fetch")

        def http_get(url):
            return FetchHttpResponse(url=url, status_code=200, text=html)

        return fetch_fixture_source_html(
            db,
            home_team,
            away_team,
            source,
            cache_dir=cache_dir,
            http_get=http_get,
        )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert calls == ["discover", "fetch"]
    assert result.status is AutoAnalyzeStatus.ANALYSIS_READY
    assert result.stage == "analyzed"
    assert result.analysis is not None
    assert result.source_link is not None
    assert result.source_link.status is SourceLinkStatus.AVAILABLE
    assert result.source_link.html_path is not None
    assert Path(result.source_link.html_path).is_file()


def test_auto_analyze_returns_fetch_blocked_when_fetch_is_blocked(tmp_path):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)

    def discovery_runner(db, home_team, away_team, source):
        return register_fixture_source_url(
            db,
            home_team,
            away_team,
            source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        return SourceLinkResult(
            status=SourceLinkStatus.BLOCKED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url="https://www.betexplorer.com/england-panama",
            warnings=("source fetch blocked by source",),
        )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.FETCH_BLOCKED
    assert result.stage == "manual_required"
    assert result.analysis is None
    assert result.source_link is not None
    assert result.source_link.status is SourceLinkStatus.BLOCKED
    assert result.warnings == ("source fetch blocked by source",)


def test_auto_analyze_default_runners_receive_requested_season(tmp_path, monkeypatch):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)
    calls = []

    def discover_fixture_source(db, home_team, away_team, source, *, season):
        calls.append(("discover", home_team, away_team, source, season))
        return SourceLinkResult(
            status=SourceLinkStatus.PENDING,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_fixture_source_html(
        db,
        home_team,
        away_team,
        source,
        cache_dir,
        *,
        season,
    ):
        calls.append(("fetch", home_team, away_team, source, cache_dir, season))
        return SourceLinkResult(
            status=SourceLinkStatus.BLOCKED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url="https://www.betexplorer.com/england-panama",
            warnings=("source fetch blocked by source",),
        )

    monkeypatch.setattr(
        auto_analysis,
        "discover_fixture_source",
        discover_fixture_source,
    )
    monkeypatch.setattr(
        auto_analysis,
        "fetch_fixture_source_html",
        fetch_fixture_source_html,
    )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        season="2026",
    )

    assert result.status is AutoAnalyzeStatus.FETCH_BLOCKED
    assert calls == [
        ("discover", "England", "Panama", "betexplorer", "2026"),
        ("fetch", "England", "Panama", "betexplorer", tmp_path / "cache", "2026"),
    ]


def test_auto_analyze_rejects_unsupported_source(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        auto_analyze_candidate(
            db,
            home_team="England",
            away_team="Panama",
            source="unknown",
            cache_dir=tmp_path / "cache",
        )
