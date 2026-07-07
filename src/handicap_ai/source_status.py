from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_discovery import normalize_source
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


DEFAULT_STATUSES = ("pending", "available", "blocked", "failed")


@dataclass(frozen=True)
class SourceFixtureStatus:
    fixture_id: int
    group_name: str
    home_team: str
    away_team: str
    source: str
    status: str
    url: str | None
    html_path: str | None
    html_available: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "group_name": self.group_name,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "source": self.source,
            "status": self.status,
            "url": self.url,
            "html_path": self.html_path,
            "html_available": self.html_available,
        }


@dataclass(frozen=True)
class SourceStatusSummary:
    source: str
    season: str
    total_fixtures: int
    by_status: dict[str, int]
    available_html: int
    fixtures: tuple[SourceFixtureStatus, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "season": self.season,
            "total_fixtures": self.total_fixtures,
            "by_status": dict(self.by_status),
            "available_html": self.available_html,
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }


def summarize_world_cup_sources(
    db: Database,
    *,
    source: str = "betexplorer",
    season: str = SEASON_2026,
) -> SourceStatusSummary:
    source_key = normalize_source(source)
    fixtures = _world_cup_fixtures(db, season)
    fixture_statuses: list[SourceFixtureStatus] = []
    status_counts: Counter[str] = Counter()
    available_html = 0

    for fixture in fixtures:
        status = _fixture_source_status(db, fixture, source_key)
        fixture_statuses.append(status)
        status_counts[status.status] += 1
        if status.html_available:
            available_html += 1

    by_status = {status: status_counts.get(status, 0) for status in DEFAULT_STATUSES}
    for status, count in sorted(status_counts.items()):
        by_status.setdefault(status, count)

    return SourceStatusSummary(
        source=source_key,
        season=season,
        total_fixtures=len(fixture_statuses),
        by_status=by_status,
        available_html=available_html,
        fixtures=tuple(fixture_statuses),
    )


def _world_cup_fixtures(db: Database, season: str):
    return db.execute(
        """
        SELECT *
        FROM tournament_fixtures
        WHERE tournament = ? AND season = ?
        ORDER BY group_name ASC, kickoff_time ASC, fixture_id ASC
        """,
        (FIFA_WORLD_CUP, season),
    )


def _fixture_source_status(db: Database, fixture, source: str) -> SourceFixtureStatus:
    source_link = next(
        (
            link
            for link in db.list_fixture_source_links(int(fixture["fixture_id"]))
            if str(link["source"]) == source
        ),
        None,
    )
    status = str(source_link["status"]) if source_link else "pending"
    html_path = source_link["html_path"] if source_link else None
    html_available = bool(html_path and Path(str(html_path)).is_file())
    return SourceFixtureStatus(
        fixture_id=int(fixture["fixture_id"]),
        group_name=str(fixture["group_name"]),
        home_team=str(fixture["home_team"]),
        away_team=str(fixture["away_team"]),
        source=source,
        status=status,
        url=source_link["url"] if source_link else None,
        html_path=str(html_path) if html_path else None,
        html_available=html_available,
    )
