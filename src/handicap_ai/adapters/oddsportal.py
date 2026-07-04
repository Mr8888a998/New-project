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


class OddsPortalHtmlAdapter:
    source_name = "oddsportal"

    def __init__(self, html_path: Path):
        self.html_path = Path(html_path)

    def load_one(self) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        return self.parse_html(self.html_path.read_text(encoding="utf-8"))

    def parse_html(self, html: str) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one("[data-op-match-id]")
        if root is None:
            raise ValueError("missing OddsPortal match container")

        source_match_id = root["data-op-match-id"]
        home, away = _split_title(_required_text(root, '[data-op-role="match-title"]'))
        competition = _required_text(root, '[data-op-role="competition"]')
        kickoff = datetime.fromisoformat(
            _required_text(root, '[data-op-role="kickoff"]')
        )
        season = str(kickoff.year)

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
        for row in root.select('table[data-op-market="1x2"] tr[data-op-snapshot]'):
            bookmaker, home, draw, away = _row_cells(row, 4)
            snapshot = row["data-op-snapshot"]
            records.append(
                OneXTwoLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=bookmaker,
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    home_win_price=float(home),
                    draw_price=float(draw),
                    away_win_price=float(away),
                )
            )
        return records

    def _parse_asian_handicaps(
        self, source_match_id: str, root: Any
    ) -> list[AsianHandicapLineRecord]:
        records: list[AsianHandicapLineRecord] = []
        for row in root.select(
            'table[data-op-market="asian_handicap"] tr[data-op-snapshot]'
        ):
            bookmaker, line, home, away = _row_cells(row, 4)
            snapshot = row["data-op-snapshot"]
            records.append(
                AsianHandicapLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=bookmaker,
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    line=float(line),
                    home_price=float(home),
                    away_price=float(away),
                )
            )
        return records

    def _parse_totals(
        self, source_match_id: str, root: Any
    ) -> list[TotalsLineRecord]:
        records: list[TotalsLineRecord] = []
        for row in root.select('table[data-op-market="totals"] tr[data-op-snapshot]'):
            bookmaker, total, over, under = _row_cells(row, 4)
            snapshot = row["data-op-snapshot"]
            records.append(
                TotalsLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker=bookmaker,
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    total=float(total),
                    over_price=float(over),
                    under_price=float(under),
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
    parts = [part.strip() for part in title.split(" v ", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"match title must use 'Home v Away': {title!r}")
    return parts[0], parts[1]


def _row_cells(row: Any, expected: int) -> list[str]:
    cells = [cell.get_text(strip=True) for cell in row.select("td")]
    if len(cells) != expected:
        raise ValueError(f"expected {expected} odds cells, got {len(cells)}")
    return cells
