from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from handicap_ai.database import Database
from handicap_ai.source_matrix import DEFAULT_MATRIX_SOURCES, SourceCell, build_source_matrix
from handicap_ai.world_cup_seed import SEASON_2026


SOURCE_CHECK_ACTIONS = (
    "ready",
    "needs_fetch",
    "missing_html",
    "needs_url",
    "blocked",
    "failed",
)

ACTION_PRIORITY = {
    "needs_fetch": 10,
    "missing_html": 20,
    "needs_url": 30,
    "blocked": 40,
    "failed": 50,
    "ready": 90,
}


@dataclass(frozen=True)
class SourceCheck:
    fixture_id: int
    group_name: str
    home_team: str
    away_team: str
    source: str
    status: str
    action: str
    reason: str
    url: str | None
    html_path: str | None
    html_available: bool
    priority: int

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "group_name": self.group_name,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "source": self.source,
            "status": self.status,
            "action": self.action,
            "reason": self.reason,
            "url": self.url,
            "html_path": self.html_path,
            "html_available": self.html_available,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class SourceCheckReport:
    season: str
    total_fixtures: int
    total_checks: int
    by_action: dict[str, int]
    checks: tuple[SourceCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "season": self.season,
            "total_fixtures": self.total_fixtures,
            "total_checks": self.total_checks,
            "by_action": dict(self.by_action),
            "checks": [check.to_dict() for check in self.checks],
        }


def build_source_checks(
    db: Database,
    *,
    sources: Sequence[str] = DEFAULT_MATRIX_SOURCES,
    season: str = SEASON_2026,
    action: str | None = None,
    limit: int | None = None,
) -> SourceCheckReport:
    matrix = build_source_matrix(db, sources=sources, season=season)
    all_checks = tuple(
        _source_check(
            fixture_id=fixture.fixture_id,
            group_name=fixture.group_name,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            cell=cell,
        )
        for fixture in matrix.fixtures
        for cell in fixture.sources.values()
    )
    counts = Counter(check.action for check in all_checks)
    filtered = (
        tuple(check for check in all_checks if check.action == action)
        if action
        else all_checks
    )
    sorted_checks = tuple(
        sorted(
            filtered,
            key=lambda check: (
                check.priority,
                check.group_name,
                check.fixture_id,
                check.source,
            ),
        )
    )
    if limit is not None:
        sorted_checks = sorted_checks[:limit]
    return SourceCheckReport(
        season=season,
        total_fixtures=matrix.total_fixtures,
        total_checks=matrix.total_source_cells,
        by_action=_action_counts(counts),
        checks=sorted_checks,
    )


def _source_check(
    *,
    fixture_id: int,
    group_name: str,
    home_team: str,
    away_team: str,
    cell: SourceCell,
) -> SourceCheck:
    action, reason = _action_and_reason(cell)
    return SourceCheck(
        fixture_id=fixture_id,
        group_name=group_name,
        home_team=home_team,
        away_team=away_team,
        source=cell.source,
        status=cell.status,
        action=action,
        reason=reason,
        url=cell.url,
        html_path=cell.html_path,
        html_available=cell.html_available,
        priority=ACTION_PRIORITY[action],
    )


def _action_and_reason(cell: SourceCell) -> tuple[str, str]:
    if cell.html_available:
        return "ready", "Cached HTML is available for analysis"
    if cell.status == "blocked":
        return "blocked", "Source request was blocked; use manual URL or HTML fallback"
    if cell.status == "failed":
        return "failed", "Last source attempt failed; retry discovery or use manual HTML"
    if cell.status == "missing_html":
        return "missing_html", "Cached HTML path is missing on disk; fetch or upload HTML again"
    if cell.url:
        return "needs_fetch", "Fetch registered source URL to create cached HTML"
    return "needs_url", "Register or discover a source URL before fetching HTML"


def _action_counts(counter: Counter[str]) -> dict[str, int]:
    counts = {action: counter.get(action, 0) for action in SOURCE_CHECK_ACTIONS}
    for action, count in sorted(counter.items()):
        counts.setdefault(action, count)
    return counts
