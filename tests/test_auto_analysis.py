from pathlib import Path

import pytest

from handicap_ai.auto_analysis import AutoAnalyzeStatus, auto_analyze_candidate
from handicap_ai.database import Database
from handicap_ai.source_discovery import SourceLinkResult
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
