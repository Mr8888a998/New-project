from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MatchCandidate:
    source: str
    source_match_id: str
    home_team: str
    away_team: str
    kickoff_time: datetime | None
    url: str


@dataclass(frozen=True)
class SourceFetchRecord:
    source: str
    url: str
    fetched_at: datetime
    status_code: int | None
    cache_path: str | None
    content_hash: str | None
    error_message: str | None

    @property
    def ok(self) -> bool:
        return (
            self.error_message is None
            and self.status_code is not None
            and 200 <= self.status_code < 300
        )


@dataclass(frozen=True)
class MarketCoverage:
    found: bool
    rows: int


@dataclass(frozen=True)
class SourceCoverage:
    source: str
    one_x_two: MarketCoverage
    handicap: MarketCoverage
    totals: MarketCoverage
    warnings: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.one_x_two.found and self.handicap.found and self.totals.found

    @property
    def missing_markets(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.one_x_two.found:
            missing.append("1x2")
        if not self.handicap.found:
            missing.append("handicap")
        if not self.totals.found:
            missing.append("totals")
        return tuple(missing)

    @property
    def risk_tags(self) -> tuple[str, ...]:
        tags: list[str] = []
        if self.missing_markets:
            tags.append("scrape_market_missing")
        if self.warnings:
            tags.append("scrape_table_untrusted")
        return tuple(tags)


@dataclass(frozen=True)
class WizardState:
    candidates: tuple[MatchCandidate, ...]
    coverage: SourceCoverage | None

    @property
    def needs_confirmation(self) -> bool:
        return len(self.candidates) != 1 or (
            self.coverage is not None and not self.coverage.is_complete
        )

    @property
    def reason(self) -> str:
        if len(self.candidates) > 1:
            return "multiple candidate matches found"
        if len(self.candidates) == 0:
            return "no candidate match found"
        if self.coverage is not None and not self.coverage.is_complete:
            return "scraped markets are incomplete"
        return "ready"
