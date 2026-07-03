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


REQUIRED_FIELDS = ("Div", "Date", "HomeTeam", "AwayTeam")


class FootballDataCsvAdapter:
    source_name = "football-data"

    def __init__(self, csv_path: Path, season: str):
        self.csv_path = Path(csv_path)
        self.season = season

    def load(self) -> list[NormalizedMatchBundle]:
        with self.csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            self._validate_headers(reader.fieldnames)
            return [
                self._row_to_bundle(row, row_number)
                for row_number, row in enumerate(reader, start=2)
            ]

    def _validate_headers(self, fieldnames: list[str] | None) -> None:
        headers = set(fieldnames or [])
        missing = [field for field in REQUIRED_FIELDS if field not in headers]
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"football-data CSV missing required header(s): {names}"
            )

    def _row_to_bundle(
        self,
        row: dict[str, str],
        row_number: int,
    ) -> NormalizedMatchBundle:
        competition = self._required_value(row, "Div", row_number)
        home = self._required_value(row, "HomeTeam", row_number)
        away = self._required_value(row, "AwayTeam", row_number)
        kickoff_time = self._required_date(row, row_number)
        source_match_id = self._source_match_id(competition, home, away, kickoff_time)
        home_score = _int_or_none(row.get("FTHG"))
        away_score = _int_or_none(row.get("FTAG"))
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=competition,
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

    def _required_value(
        self,
        row: dict[str, str],
        field_name: str,
        row_number: int,
    ) -> str:
        value = _clean_value(row.get(field_name))
        if value is None:
            raise ValueError(
                f"football-data row {row_number}: required field "
                f"{field_name} is blank"
            )
        return value

    def _required_date(
        self,
        row: dict[str, str],
        row_number: int,
    ) -> datetime:
        value = self._required_value(row, "Date", row_number)
        parsed = _parse_date(value)
        if parsed is None:
            raise ValueError(
                f"football-data row {row_number}: Date {value!r} does not "
                "match supported formats %d/%m/%y, %d/%m/%Y, or %Y-%m-%d"
            )
        return parsed

    def _asian_handicaps(
        self,
        source_match_id: str,
        row: dict[str, str],
    ) -> list[AsianHandicapLineRecord]:
        line = _float_or_none(_first_value(row, ("AHCh", "AHh")))
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
                home_price=_float_or_none(
                    _first_value(row, ("B365CAHH", "B365AHH"))
                ),
                away_price=_float_or_none(
                    _first_value(row, ("B365CAHA", "B365AHA"))
                ),
            )
        ]

    def _totals(
        self,
        source_match_id: str,
        row: dict[str, str],
    ) -> list[TotalsLineRecord]:
        over_price = _float_or_none(_first_value(row, ("Avg>2.5", "BbAv>2.5")))
        under_price = _float_or_none(_first_value(row, ("Avg<2.5", "BbAv<2.5")))
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
        home_price = _float_or_none(_first_value(row, ("B365CH", "B365H")))
        draw_price = _float_or_none(_first_value(row, ("B365CD", "B365D")))
        away_price = _float_or_none(_first_value(row, ("B365CA", "B365A")))
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
        competition: str,
        home: str,
        away: str,
        kickoff_time: datetime,
    ) -> str:
        div = _slug(competition)
        date_part = kickoff_time.date().isoformat()
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


def _first_value(row: dict[str, str], field_names: tuple[str, ...]) -> str | None:
    for field_name in field_names:
        value = _clean_value(row.get(field_name))
        if value is not None:
            return value
    return None


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _slug(value: str) -> str:
    normalized = normalize_team_name(value)
    return normalized.replace(" ", "-") or "unknown"
