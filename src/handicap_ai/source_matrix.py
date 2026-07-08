from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

from handicap_ai.database import Database
from handicap_ai.source_discovery import normalize_source
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


DEFAULT_MATRIX_SOURCES = ("betexplorer", "oddsportal")
MATRIX_STATUSES = ("pending", "available", "missing_html", "blocked", "failed")


@dataclass(frozen=True)
class SourceCell:
    source: str
    status: str
    url: str | None
    html_path: str | None
    html_available: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "url": self.url,
            "html_path": self.html_path,
            "html_available": self.html_available,
        }


@dataclass(frozen=True)
class SourceMatrixFixture:
    fixture_id: int
    group_name: str
    home_team: str
    away_team: str
    sources: dict[str, SourceCell]

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "group_name": self.group_name,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "sources": {
                source: cell.to_dict()
                for source, cell in self.sources.items()
            },
        }


@dataclass(frozen=True)
class SourceMatrixSourceSummary:
    source: str
    total: int
    by_status: dict[str, int]
    available_html: int
    registered_urls: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "total": self.total,
            "by_status": dict(self.by_status),
            "available_html": self.available_html,
            "registered_urls": self.registered_urls,
        }


@dataclass(frozen=True)
class SourceMatrix:
    season: str
    total_fixtures: int
    total_source_cells: int
    sources: dict[str, SourceMatrixSourceSummary]
    fixtures: tuple[SourceMatrixFixture, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "season": self.season,
            "total_fixtures": self.total_fixtures,
            "total_source_cells": self.total_source_cells,
            "sources": {
                source: summary.to_dict()
                for source, summary in self.sources.items()
            },
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }


def build_source_matrix(
    db: Database,
    *,
    sources: Sequence[str] = DEFAULT_MATRIX_SOURCES,
    season: str = SEASON_2026,
) -> SourceMatrix:
    source_keys = tuple(dict.fromkeys(normalize_source(source) for source in sources))
    fixture_rows = _world_cup_fixtures(db, season)
    fixtures: list[SourceMatrixFixture] = []
    counters = {source: Counter() for source in source_keys}
    available_html = Counter()
    registered_urls = Counter()

    for fixture in fixture_rows:
        cells: dict[str, SourceCell] = {}
        source_links = {
            str(link["source"]): link
            for link in db.list_fixture_source_links(int(fixture["fixture_id"]))
        }
        for source in source_keys:
            cell = _source_cell(source, source_links.get(source))
            cells[source] = cell
            counters[source][cell.status] += 1
            if cell.html_available:
                available_html[source] += 1
            if cell.url:
                registered_urls[source] += 1
        fixtures.append(
            SourceMatrixFixture(
                fixture_id=int(fixture["fixture_id"]),
                group_name=str(fixture["group_name"]),
                home_team=str(fixture["home_team"]),
                away_team=str(fixture["away_team"]),
                sources=cells,
            )
        )

    source_summaries = {
        source: SourceMatrixSourceSummary(
            source=source,
            total=len(fixtures),
            by_status=_status_counts(counters[source]),
            available_html=available_html[source],
            registered_urls=registered_urls[source],
        )
        for source in source_keys
    }
    return SourceMatrix(
        season=season,
        total_fixtures=len(fixtures),
        total_source_cells=len(fixtures) * len(source_keys),
        sources=source_summaries,
        fixtures=tuple(fixtures),
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


def _source_cell(source: str, link) -> SourceCell:
    if link is None:
        return SourceCell(
            source=source,
            status="pending",
            url=None,
            html_path=None,
            html_available=False,
        )

    status = str(link["status"])
    html_path = link["html_path"]
    html_available = bool(html_path and Path(str(html_path)).is_file())
    if status == "available" and not html_available:
        status = "missing_html"
    return SourceCell(
        source=source,
        status=status,
        url=link["url"],
        html_path=str(html_path) if html_path else None,
        html_available=html_available,
    )


def _status_counts(counter: Counter[str]) -> dict[str, int]:
    counts = {status: counter.get(status, 0) for status in MATRIX_STATUSES}
    for status, count in sorted(counter.items()):
        counts.setdefault(status, count)
    return counts
