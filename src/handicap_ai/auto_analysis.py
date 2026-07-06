from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from handicap_ai.candidate_search import (
    CandidateStatus,
    FixtureCandidate,
    find_world_cup_candidates,
)
from handicap_ai.database import Database
from handicap_ai.live_analysis import LiveAnalysisResult, analyze_saved_html
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    discover_fixture_source,
    normalize_source,
)
from handicap_ai.source_fetch import fetch_fixture_source_html
from handicap_ai.world_cup_seed import SEASON_2026


class AutoAnalyzeStatus(str, Enum):
    ANALYSIS_READY = "analysis_ready"
    INVALID_TEAM = "invalid_team"
    NOT_IN_GROUP_STAGE = "not_in_group_stage"
    NEEDS_MANUAL_SOURCE = "needs_manual_source"
    SOURCE_PENDING = "source_pending"
    FETCH_BLOCKED = "fetch_blocked"
    FETCH_FAILED = "fetch_failed"


DiscoveryRunner = Callable[[Database, str, str, str], SourceLinkResult]
FetchRunner = Callable[[Database, str, str, str, str | Path], SourceLinkResult]


@dataclass(frozen=True)
class AutoAnalyzeResult:
    status: AutoAnalyzeStatus
    stage: str
    warnings: tuple[str, ...]
    candidate: FixtureCandidate | None
    source_link: SourceLinkResult | None
    analysis: LiveAnalysisResult | None


def default_discovery_runner(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    return discover_fixture_source(
        db,
        home_team,
        away_team,
        source,
        season=season,
    )


def default_fetch_runner(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: str | Path,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    return fetch_fixture_source_html(
        db,
        home_team,
        away_team,
        source,
        cache_dir,
        season=season,
    )


def _analysis_ready(
    db: Database,
    candidate: FixtureCandidate,
    source_link: SourceLinkResult,
) -> AutoAnalyzeResult:
    analysis = analyze_saved_html(
        db,
        source_link.source,
        Path(source_link.html_path),
    )
    return AutoAnalyzeResult(
        status=AutoAnalyzeStatus.ANALYSIS_READY,
        stage="analyzed",
        warnings=source_link.warnings,
        candidate=candidate,
        source_link=source_link,
        analysis=analysis,
    )


def _manual_result(
    candidate: FixtureCandidate | None,
    source_link: SourceLinkResult,
) -> AutoAnalyzeResult:
    return AutoAnalyzeResult(
        status=_status_for_source_link(source_link),
        stage="manual_required",
        warnings=source_link.warnings,
        candidate=candidate,
        source_link=source_link,
        analysis=None,
    )


def _status_for_source_link(source_link: SourceLinkResult) -> AutoAnalyzeStatus:
    if source_link.status is SourceLinkStatus.BLOCKED:
        return AutoAnalyzeStatus.FETCH_BLOCKED
    if source_link.status is SourceLinkStatus.FAILED:
        return AutoAnalyzeStatus.FETCH_FAILED
    if source_link.status is SourceLinkStatus.PENDING:
        return AutoAnalyzeStatus.SOURCE_PENDING
    return AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE


def _has_existing_html(source_link: SourceLinkResult) -> bool:
    return source_link.html_path is not None and Path(source_link.html_path).is_file()


def _with_missing_html_warning(source_link: SourceLinkResult) -> SourceLinkResult:
    missing_warning = (
        f"available HTML missing on disk: {source_link.html_path}"
        if source_link.html_path
        else "available HTML missing on disk"
    )
    if any("missing" in warning.lower() for warning in source_link.warnings):
        return source_link
    return SourceLinkResult(
        status=source_link.status,
        fixture_id=source_link.fixture_id,
        source=source_link.source,
        html_path=source_link.html_path,
        url=source_link.url,
        warnings=(*source_link.warnings, missing_warning),
    )


def auto_analyze_candidate(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: str | Path,
    discovery_runner: DiscoveryRunner | None = None,
    fetch_runner: FetchRunner | None = None,
    season: str = SEASON_2026,
) -> AutoAnalyzeResult:
    candidate_result = find_world_cup_candidates(
        db,
        home_team=home_team,
        away_team=away_team,
        season=season,
    )
    if candidate_result.status is CandidateStatus.INVALID_TEAM:
        return AutoAnalyzeResult(
            status=AutoAnalyzeStatus.INVALID_TEAM,
            stage="candidate_checked",
            warnings=candidate_result.warnings,
            candidate=None,
            source_link=None,
            analysis=None,
        )
    if candidate_result.status is CandidateStatus.NOT_IN_GROUP_STAGE:
        return AutoAnalyzeResult(
            status=AutoAnalyzeStatus.NOT_IN_GROUP_STAGE,
            stage="candidate_checked",
            warnings=candidate_result.warnings,
            candidate=None,
            source_link=None,
            analysis=None,
        )

    source_key = normalize_source(source)
    candidate = candidate_result.candidates[0] if candidate_result.candidates else None
    if candidate is not None:
        link = candidate.sources.get(source_key)
        if (
            link is not None
            and link.status == SourceLinkStatus.AVAILABLE.value
            and link.html_path
            and Path(link.html_path).is_file()
        ):
            source_link = SourceLinkResult(
                status=SourceLinkStatus.AVAILABLE,
                fixture_id=candidate.fixture_id,
                source=source_key,
                html_path=link.html_path,
                url=link.url,
            )
            return _analysis_ready(db, candidate, source_link)

    if discovery_runner is None:
        discovered = default_discovery_runner(
            db,
            home_team,
            away_team,
            source_key,
            season=season,
        )
    else:
        discovered = discovery_runner(db, home_team, away_team, source_key)
    if discovered.status is SourceLinkStatus.AVAILABLE:
        if _has_existing_html(discovered):
            return _analysis_ready(db, candidate, discovered)
        return _manual_result(candidate, _with_missing_html_warning(discovered))
    if discovered.url is None:
        return _manual_result(candidate, discovered)

    if fetch_runner is None:
        fetched = default_fetch_runner(
            db,
            home_team,
            away_team,
            source_key,
            cache_dir,
            season=season,
        )
    else:
        fetched = fetch_runner(db, home_team, away_team, source_key, cache_dir)
    if fetched.status is SourceLinkStatus.AVAILABLE:
        if _has_existing_html(fetched):
            return _analysis_ready(db, candidate, fetched)
        return _manual_result(candidate, _with_missing_html_warning(fetched))
    return _manual_result(candidate, fetched)
