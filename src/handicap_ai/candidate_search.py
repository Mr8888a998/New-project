from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType

from handicap_ai.database import Database
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


class CandidateStatus(str, Enum):
    READY = "ready"
    NEEDS_HTML = "needs_html"
    INVALID_TEAM = "invalid_team"
    NOT_IN_GROUP_STAGE = "not_in_group_stage"


@dataclass(frozen=True)
class SourceLinkCandidate:
    source: str
    status: str
    html_path: str | None
    url: str | None


@dataclass(frozen=True)
class FixtureCandidate:
    fixture_id: int
    group_name: str
    home_team: str
    away_team: str
    kickoff_time: str | None
    status: str
    sources: Mapping[str, SourceLinkCandidate]


@dataclass(frozen=True)
class CandidateSearchResult:
    status: CandidateStatus
    candidates: tuple[FixtureCandidate, ...]
    warnings: tuple[str, ...]


def find_world_cup_candidates(
    db: Database,
    home_team: str,
    away_team: str,
    season: str = SEASON_2026,
) -> CandidateSearchResult:
    resolved_home = db.resolve_tournament_team(FIFA_WORLD_CUP, season, home_team)
    resolved_away = db.resolve_tournament_team(FIFA_WORLD_CUP, season, away_team)

    warnings = []
    if resolved_home is None:
        warnings.append(f"Unknown team: {home_team}")
    if resolved_away is None:
        warnings.append(f"Unknown team: {away_team}")
    if warnings:
        return CandidateSearchResult(
            status=CandidateStatus.INVALID_TEAM,
            candidates=(),
            warnings=tuple(warnings),
        )

    fixture_rows = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        season,
        resolved_home["team_name"],
        resolved_away["team_name"],
    )
    if not fixture_rows:
        return CandidateSearchResult(
            status=CandidateStatus.NOT_IN_GROUP_STAGE,
            candidates=(),
            warnings=("Both teams are seeded, but no group-stage fixture was found",),
        )

    candidates = tuple(_fixture_candidate(db, row) for row in fixture_rows)
    status = (
        CandidateStatus.READY
        if any(
            _has_available_html(source)
            for candidate in candidates
            for source in candidate.sources.values()
        )
        else CandidateStatus.NEEDS_HTML
    )
    return CandidateSearchResult(status=status, candidates=candidates, warnings=())


def _has_available_html(link: SourceLinkCandidate) -> bool:
    """Relative html paths are resolved from the current process working directory."""
    return (
        link.status == "available"
        and bool(link.html_path)
        and Path(link.html_path).is_file()
    )


def _fixture_candidate(db: Database, row: sqlite3.Row) -> FixtureCandidate:
    sources = {
        link["source"]: SourceLinkCandidate(
            source=link["source"],
            status=link["status"],
            html_path=link["html_path"],
            url=link["url"],
        )
        for link in db.list_fixture_source_links(int(row["fixture_id"]))
    }
    return FixtureCandidate(
        fixture_id=int(row["fixture_id"]),
        group_name=row["group_name"],
        home_team=row["home_team"],
        away_team=row["away_team"],
        kickoff_time=row["kickoff_time"],
        status=row["status"],
        sources=MappingProxyType(sources),
    )
