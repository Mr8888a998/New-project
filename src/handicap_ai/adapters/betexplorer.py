from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    NormalizedMatchBundle,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.scraping.models import MarketCoverage, SourceCoverage


class BetExplorerHtmlAdapter:
    source_name = "betexplorer"

    def __init__(self, html_path: Path):
        self.html_path = Path(html_path)

    def load_one(self) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        return self.parse_html(self.html_path.read_text(encoding="utf-8"))

    def parse_html(self, html: str) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one('main[data-source="betexplorer"][data-match-id]')
        if root is None:
            raise ValueError("missing BetExplorer match container")

        source_match_id = root["data-match-id"]
        home, away = _split_title(_required_text(root, ".list-breadcrumb__item__in"))
        competition = _required_text(root, ".list-details__item")
        kickoff = _parse_kickoff(root.select_one("time[datetime]"))
        season = str(kickoff.year) if kickoff is not None else "unknown"

        one_x_two = tuple(self._parse_one_x_two(source_match_id, root))
        asian_handicaps = tuple(self._parse_asian_handicaps(source_match_id, root))
        totals = tuple(self._parse_totals(source_match_id, root))

        bundle = NormalizedMatchBundle(
            match=MatchRecord(
                source_match_id=source_match_id,
                home_team=home,
                away_team=away,
                competition=competition,
                season=season,
                kickoff_time=kickoff,
                status=MatchStatus.SCHEDULED,
            ),
            teams=(TeamRecord(home), TeamRecord(away)),
            asian_handicaps=asian_handicaps,
            totals=totals,
            one_x_two=one_x_two,
        )
        coverage = SourceCoverage(
            source=self.source_name,
            one_x_two=MarketCoverage(found=bool(one_x_two), rows=len(one_x_two)),
            handicap=MarketCoverage(
                found=bool(asian_handicaps), rows=len(asian_handicaps)
            ),
            totals=MarketCoverage(found=bool(totals), rows=len(totals)),
        )
        return bundle, coverage

    def _parse_one_x_two(
        self, source_match_id: str, root: Any
    ) -> list[OneXTwoLineRecord]:
        records: list[OneXTwoLineRecord] = []
        for row in root.select('section[data-market="1x2"] .odds-row[data-snapshot]'):
            snapshot = row["data-snapshot"]
            records.append(
                OneXTwoLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=_bookmaker(row),
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    home_win_price=_outcome_float(row, "home"),
                    draw_price=_outcome_float(row, "draw"),
                    away_win_price=_outcome_float(row, "away"),
                )
            )
        return records

    def _parse_asian_handicaps(
        self, source_match_id: str, root: Any
    ) -> list[AsianHandicapLineRecord]:
        records: list[AsianHandicapLineRecord] = []
        for row in root.select(
            'section[data-market="asian_handicap"] .odds-row[data-snapshot]'
        ):
            snapshot = row["data-snapshot"]
            records.append(
                AsianHandicapLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=_bookmaker(row),
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    line=_line_float(row),
                    home_price=_outcome_float(row, "home"),
                    away_price=_outcome_float(row, "away"),
                )
            )
        return records

    def _parse_totals(
        self, source_match_id: str, root: Any
    ) -> list[TotalsLineRecord]:
        records: list[TotalsLineRecord] = []
        for row in root.select('section[data-market="totals"] .odds-row[data-snapshot]'):
            snapshot = row["data-snapshot"]
            records.append(
                TotalsLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=_bookmaker(row),
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    total=_line_float(row),
                    over_price=_outcome_float(row, "over"),
                    under_price=_outcome_float(row, "under"),
                )
            )
        return records


def _required_text(root: Any, selector: str) -> str:
    element = root.select_one(selector)
    if element is None:
        raise ValueError(f"missing required selector {selector}")
    value = element.get_text(strip=True)
    if not value:
        raise ValueError(f"blank required selector {selector}")
    return value


def _split_title(title: str) -> tuple[str, str]:
    parts = [part.strip() for part in title.split(" - ", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"match title must use 'Home - Away': {title!r}")
    return parts[0], parts[1]


def _parse_kickoff(element: Any | None) -> datetime | None:
    if element is None:
        return None
    value = element.get("datetime")
    if not value:
        return None
    return datetime.fromisoformat(value)


def _bookmaker(row: Any) -> str:
    value = row.get("data-bookmaker", "").strip()
    return value or "unknown"


def _line_float(row: Any) -> float:
    line = row.select_one("[data-line]")
    if line is None:
        raise ValueError("missing odds row line")
    return float(line["data-line"])


def _outcome_float(row: Any, outcome: str) -> float:
    element = row.select_one(f'[data-outcome="{outcome}"]')
    if element is None:
        raise ValueError(f"missing odds row outcome {outcome}")
    return float(element.get_text(strip=True))
