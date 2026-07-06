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


DiscoveryRunner = Callable[..., SourceLinkResult]
FetchRunner = Callable[..., SourceLinkResult]


@dataclass(frozen=True)
class AutoAnalyzeResult:
    status: AutoAnalyzeStatus
    stage: str
    warnings: tuple[str, ...]
    candidate: FixtureCandidate | None
    source_link: SourceLinkResult | None
    analysis: LiveAnalysisResult | None


def default_discovery_runner(*args, **kwargs) -> SourceLinkResult:
    return discover_fixture_source(*args, **kwargs)


def default_fetch_runner(*args, **kwargs) -> SourceLinkResult:
    return fetch_fixture_source_html(*args, **kwargs)


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

    source_key = source.strip().lower()
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
            analysis = analyze_saved_html(
                db,
                source_link.source,
                Path(source_link.html_path),
            )
            return AutoAnalyzeResult(
                status=AutoAnalyzeStatus.ANALYSIS_READY,
                stage="analyzed",
                warnings=(),
                candidate=candidate,
                source_link=source_link,
                analysis=analysis,
            )

    return AutoAnalyzeResult(
        status=AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE,
        stage="manual_required",
        warnings=("No cached HTML found",),
        candidate=candidate,
        source_link=None,
        analysis=None,
    )
