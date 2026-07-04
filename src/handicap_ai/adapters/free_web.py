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


class FreeWebHtmlAdapter:
    def __init__(self, source_name: str, html_path: Path):
        self.source_name = source_name
        self.html_path = Path(html_path)

    def load(self) -> list[NormalizedMatchBundle]:
        soup = BeautifulSoup(self.html_path.read_text(encoding="utf-8"), "html.parser")
        return [
            self._parse_article(article)
            for article in soup.select("article[data-match-id]")
        ]

    def _parse_article(self, article: Any) -> NormalizedMatchBundle:
        title = _required_text(article, '[data-role="match-title"]')
        home, away = _split_title(title)
        source_match_id = article["data-match-id"]
        competition = _required_text(article, '[data-role="competition"]')
        season = _required_text(article, '[data-role="season"]')
        kickoff = datetime.fromisoformat(_required_text(article, '[data-role="kickoff"]'))
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=competition,
            season=season,
            kickoff_time=kickoff,
            status=MatchStatus.SCHEDULED,
        )
        return NormalizedMatchBundle(
            match=match,
            teams=(TeamRecord(home), TeamRecord(away)),
            asian_handicaps=tuple(self._parse_asian(source_match_id, article)),
            totals=tuple(self._parse_totals(source_match_id, article)),
            one_x_two=tuple(self._parse_one_x_two(source_match_id, article)),
        )

    def _parse_asian(
        self, source_match_id: str, article: Any
    ) -> list[AsianHandicapLineRecord]:
        rows = article.select('table[data-market="asian_handicap"] tr[data-snapshot]')
        records: list[AsianHandicapLineRecord] = []
        for row in rows:
            cells = _cells(row, expected=3)
            snapshot = row["data-snapshot"]
            records.append(
                AsianHandicapLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    line=float(cells[0]),
                    home_price=float(cells[1]),
                    away_price=float(cells[2]),
                )
            )
        return records

    def _parse_totals(
        self, source_match_id: str, article: Any
    ) -> list[TotalsLineRecord]:
        rows = article.select('table[data-market="totals"] tr[data-snapshot]')
        records: list[TotalsLineRecord] = []
        for row in rows:
            cells = _cells(row, expected=3)
            snapshot = row["data-snapshot"]
            records.append(
                TotalsLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    total=float(cells[0]),
                    over_price=float(cells[1]),
                    under_price=float(cells[2]),
                )
            )
        return records

    def _parse_one_x_two(
        self, source_match_id: str, article: Any
    ) -> list[OneXTwoLineRecord]:
        rows = article.select('table[data-market="1x2"] tr[data-snapshot]')
        records: list[OneXTwoLineRecord] = []
        for row in rows:
            cells = _cells(row, expected=3)
            snapshot = row["data-snapshot"]
            records.append(
                OneXTwoLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    home_win_price=float(cells[0]),
                    draw_price=float(cells[1]),
                    away_win_price=float(cells[2]),
                )
            )
        return records


def _required_text(article: Any, selector: str) -> str:
    element = article.select_one(selector)
    if element is None:
        raise ValueError(f"missing required selector {selector}")
    value = element.get_text(strip=True)
    if not value:
        raise ValueError(f"blank required selector {selector}")
    return value


def _split_title(title: str) -> tuple[str, str]:
    try:
        home, away = [part.strip() for part in title.split(" - ", 1)]
    except ValueError as exc:
        raise ValueError(f"match title must use 'Home - Away': {title!r}") from exc
    if not home or not away:
        raise ValueError(f"match title must include both teams: {title!r}")
    return home, away


def _cells(row: Any, expected: int) -> list[str]:
    cells = [cell.get_text(strip=True) for cell in row.select("td")]
    if len(cells) != expected or any(cell == "" for cell in cells):
        raise ValueError(f"expected {expected} populated cells in odds row")
    return cells
