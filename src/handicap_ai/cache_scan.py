from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.source_discovery import normalize_source


CACHE_SCAN_STATUSES = (
    "linked",
    "orphan",
    "invalid",
    "unknown_source",
)

STATUS_PRIORITY = {
    "linked": 10,
    "invalid": 20,
    "orphan": 30,
    "unknown_source": 40,
}


@dataclass(frozen=True)
class CacheFileCheck:
    path: str
    source: str
    status: str
    linked: bool
    parseable: bool
    coverage_complete: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "source": self.source,
            "status": self.status,
            "linked": self.linked,
            "parseable": self.parseable,
            "coverage_complete": self.coverage_complete,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MissingCacheLink:
    fixture_id: int
    home_team: str | None
    away_team: str | None
    source: str
    html_path: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "source": self.source,
            "html_path": self.html_path,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CacheScanReport:
    cache_dir: str
    total_files: int
    linked_files: int
    orphan_files: int
    parseable_files: int
    invalid_files: int
    missing_linked_files: int
    by_status: dict[str, int]
    files: tuple[CacheFileCheck, ...]
    missing_links: tuple[MissingCacheLink, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_dir": self.cache_dir,
            "total_files": self.total_files,
            "linked_files": self.linked_files,
            "orphan_files": self.orphan_files,
            "parseable_files": self.parseable_files,
            "invalid_files": self.invalid_files,
            "missing_linked_files": self.missing_linked_files,
            "by_status": dict(self.by_status),
            "files": [file.to_dict() for file in self.files],
            "missing_links": [link.to_dict() for link in self.missing_links],
        }


def scan_cache_html(
    db: Database,
    *,
    cache_dir: str | Path,
    limit: int | None = None,
) -> CacheScanReport:
    cache_root = Path(cache_dir)
    source_links = _source_links_with_html(db)
    linked_sources = {
        _resolved_path(str(row["html_path"])): normalize_source(str(row["source"]))
        for row in source_links
        if row["html_path"]
    }
    files = tuple(_html_files(cache_root))
    checks = tuple(_cache_file_check(cache_root, path, linked_sources) for path in files)
    missing_links = tuple(
        _missing_link(row)
        for row in source_links
        if row["html_path"] and not Path(str(row["html_path"])).is_file()
    )
    counts = Counter(check.status for check in checks)
    sorted_checks = tuple(
        sorted(
            checks,
            key=lambda check: (
                STATUS_PRIORITY.get(check.status, 99),
                check.source,
                check.path,
            ),
        )
    )
    if limit is not None:
        sorted_checks = sorted_checks[:limit]
    return CacheScanReport(
        cache_dir=str(cache_root),
        total_files=len(files),
        linked_files=sum(1 for check in checks if check.linked),
        orphan_files=sum(1 for check in checks if not check.linked),
        parseable_files=sum(1 for check in checks if check.parseable),
        invalid_files=sum(1 for check in checks if not check.parseable),
        missing_linked_files=len(missing_links),
        by_status=_status_counts(counts),
        files=sorted_checks,
        missing_links=missing_links,
    )


def _html_files(cache_root: Path) -> list[Path]:
    if not cache_root.exists():
        return []
    return sorted(path for path in cache_root.rglob("*.html") if path.is_file())


def _cache_file_check(
    cache_root: Path,
    path: Path,
    linked_sources: dict[Path, str],
) -> CacheFileCheck:
    resolved = _resolved_path(path)
    linked = resolved in linked_sources
    source = linked_sources.get(resolved) or _source_from_cache_path(cache_root, path)
    adapter = _adapter_for_source(source)
    if adapter is None:
        return CacheFileCheck(
            path=str(path),
            source=source,
            status="unknown_source",
            linked=linked,
            parseable=False,
            coverage_complete=False,
            reason="cache file is not under a supported source folder",
        )
    try:
        _bundle, coverage = adapter(path).load_one()
    except ValueError as error:
        return CacheFileCheck(
            path=str(path),
            source=source,
            status="invalid",
            linked=linked,
            parseable=False,
            coverage_complete=False,
            reason=str(error),
        )
    return CacheFileCheck(
        path=str(path),
        source=source,
        status="linked" if linked else "orphan",
        linked=linked,
        parseable=True,
        coverage_complete=coverage.is_complete,
        reason="cache file is linked to a fixture" if linked else "cache file is not linked to a fixture",
    )


def _source_links_with_html(db: Database):
    return db.execute(
        """
        SELECT
          fixture_source_links.fixture_id,
          fixture_source_links.source,
          fixture_source_links.html_path,
          tournament_fixtures.home_team,
          tournament_fixtures.away_team
        FROM fixture_source_links
        LEFT JOIN tournament_fixtures
          ON tournament_fixtures.fixture_id = fixture_source_links.fixture_id
        WHERE fixture_source_links.html_path IS NOT NULL
          AND fixture_source_links.html_path != ''
        ORDER BY fixture_source_links.fixture_id ASC, fixture_source_links.source ASC
        """
    )


def _missing_link(row) -> MissingCacheLink:
    return MissingCacheLink(
        fixture_id=int(row["fixture_id"]),
        home_team=row["home_team"],
        away_team=row["away_team"],
        source=normalize_source(str(row["source"])),
        html_path=str(row["html_path"]),
        reason="linked HTML path is missing on disk",
    )


def _source_from_cache_path(cache_root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(cache_root)
    except ValueError:
        return ""
    return normalize_source(relative.parts[0]) if relative.parts else ""


def _adapter_for_source(source: str):
    if source == BetExplorerHtmlAdapter.source_name:
        return BetExplorerHtmlAdapter
    if source == OddsPortalHtmlAdapter.source_name:
        return OddsPortalHtmlAdapter
    return None


def _resolved_path(path: str | Path) -> Path:
    return Path(path).resolve()


def _status_counts(counter: Counter[str]) -> dict[str, int]:
    counts = {status: counter.get(status, 0) for status in CACHE_SCAN_STATUSES}
    for status, count in sorted(counter.items()):
        counts.setdefault(status, count)
    return counts
