from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    NormalizedMatchBundle,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.names import normalize_team_name


class FootballDataCsvAdapter:
    source_name = "football-data"

    def __init__(self, csv_path: Path, season: str):
        self.csv_path = Path(csv_path)
        self.season = season

    def load(self) -> list[NormalizedMatchBundle]:
        with self.csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return [self._row_to_bundle(row) for row in reader]

    def _row_to_bundle(self, row: dict[str, str]) -> NormalizedMatchBundle:
        home = row["HomeTeam"].strip()
        away = row["AwayTeam"].strip()
        kickoff_time = _parse_date(row.get("Date", ""))
        source_match_id = self._source_match_id(row, home, away, kickoff_time)
        home_score = _int_or_none(row.get("FTHG"))
        away_score = _int_or_none(row.get("FTAG"))
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=_clean_value(row.get("Div")) or "unknown",
            season=self.season,
            kickoff_time=kickoff_time,
            status=(
                MatchStatus.FINISHED
                if home_score is not None and away_score is not None
                else MatchStatus.SCHEDULED
            ),
            home_score=home_score,
            away_score=away_score,
        )
        return NormalizedMatchBundle(
            match=match,
            teams=(TeamRecord(home), TeamRecord(away)),
            asian_handicaps=tuple(self._asian_handicaps(source_match_id, row)),
            totals=tuple(self._totals(source_match_id, row)),
            one_x_two=tuple(self._one_x_two(source_match_id, row)),
        )

    def _asian_handicaps(
        self,
        source_match_id: str,
        row: dict[str, str],
    ) -> list[AsianHandicapLineRecord]:
        line = _float_or_none(row.get("AHh"))
        if line is None:
            return []
        return [
            AsianHandicapLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="B365",
                is_opening=False,
                is_closing=True,
                line=line,
                home_price=_float_or_none(row.get("B365AHH")),
                away_price=_float_or_none(row.get("B365AHA")),
            )
        ]

    def _totals(
        self,
        source_match_id: str,
        row: dict[str, str],
    ) -> list[TotalsLineRecord]:
        over_price = _float_or_none(row.get("BbAv>2.5"))
        under_price = _float_or_none(row.get("BbAv<2.5"))
        if over_price is None and under_price is None:
            return []
        return [
            TotalsLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="market-average",
                is_opening=False,
                is_closing=True,
                total=2.5,
                over_price=over_price,
                under_price=under_price,
            )
        ]

    def _one_x_two(
        self,
        source_match_id: str,
        row: dict[str, str],
    ) -> list[OneXTwoLineRecord]:
        home_price = _float_or_none(row.get("B365H"))
        draw_price = _float_or_none(row.get("B365D"))
        away_price = _float_or_none(row.get("B365A"))
        if home_price is None and draw_price is None and away_price is None:
            return []
        return [
            OneXTwoLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="B365",
                is_opening=False,
                is_closing=True,
                home_win_price=home_price,
                draw_price=draw_price,
                away_win_price=away_price,
            )
        ]

    def _source_match_id(
        self,
        row: dict[str, str],
        home: str,
        away: str,
        kickoff_time: datetime | None,
    ) -> str:
        div = _slug(_clean_value(row.get("Div")) or "unknown")
        date_part = (
            kickoff_time.date().isoformat()
            if kickoff_time is not None
            else _slug(_clean_value(row.get("Date")) or "unknown")
        )
        home_part = _slug(home)
        away_part = _slug(away)
        return (
            f"{self.source_name}:{self.season}:{div}:{date_part}:"
            f"{home_part}-{away_part}"
        )


def _parse_date(value: str | None) -> datetime | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _float_or_none(value: str | None) -> float | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    return float(cleaned)


def _int_or_none(value: str | None) -> int | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    return int(cleaned)


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _slug(value: str) -> str:
    normalized = normalize_team_name(value)
    return normalized.replace(" ", "-") or "unknown"
