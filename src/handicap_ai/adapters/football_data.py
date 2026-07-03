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
AH_CURRENT_FIELDS = ("AHCh", "B365CAHH", "B365CAHA")
AH_FALLBACK_FIELDS = ("AHh", "B365AHH", "B365AHA")
TOTAL_CURRENT_FIELDS = ("Avg>2.5", "Avg<2.5")
TOTAL_FALLBACK_FIELDS = ("BbAv>2.5", "BbAv<2.5")
ONE_X_TWO_CURRENT_FIELDS = ("B365CH", "B365CD", "B365CA")
ONE_X_TWO_FALLBACK_FIELDS = ("B365H", "B365D", "B365A")


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
        home_score = _int_field(row, "FTHG", row_number)
        away_score = _int_field(row, "FTAG", row_number)
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
            asian_handicaps=tuple(
                self._asian_handicaps(source_match_id, row, row_number)
            ),
            totals=tuple(self._totals(source_match_id, row, row_number)),
            one_x_two=tuple(self._one_x_two(source_match_id, row, row_number)),
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
        row_number: int,
    ) -> list[AsianHandicapLineRecord]:
        fields = (
            AH_CURRENT_FIELDS
            if _has_any_value(row, AH_CURRENT_FIELDS)
            else AH_FALLBACK_FIELDS
        )
        if not _has_any_value(row, fields):
            return []

        line_field, home_price_field, away_price_field = fields
        if _clean_value(row.get(line_field)) is None:
            raise ValueError(
                f"football-data row {row_number}: malformed AH snapshot; "
                f"field {line_field} is required when AH prices are present"
            )

        return [
            AsianHandicapLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="B365",
                is_opening=False,
                is_closing=True,
                line=_float_field(row, line_field, row_number),
                home_price=_float_field(row, home_price_field, row_number),
                away_price=_float_field(row, away_price_field, row_number),
            )
        ]

    def _totals(
        self,
        source_match_id: str,
        row: dict[str, str],
        row_number: int,
    ) -> list[TotalsLineRecord]:
        fields = (
            TOTAL_CURRENT_FIELDS
            if _has_any_value(row, TOTAL_CURRENT_FIELDS)
            else TOTAL_FALLBACK_FIELDS
        )
        if not _has_any_value(row, fields):
            return []

        over_field, under_field = fields
        return [
            TotalsLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="market-average",
                is_opening=False,
                is_closing=True,
                total=2.5,
                over_price=_float_field(row, over_field, row_number),
                under_price=_float_field(row, under_field, row_number),
            )
        ]

    def _one_x_two(
        self,
        source_match_id: str,
        row: dict[str, str],
        row_number: int,
    ) -> list[OneXTwoLineRecord]:
        fields = (
            ONE_X_TWO_CURRENT_FIELDS
            if _has_any_value(row, ONE_X_TWO_CURRENT_FIELDS)
            else ONE_X_TWO_FALLBACK_FIELDS
        )
        if not _has_any_value(row, fields):
            return []

        home_field, draw_field, away_field = fields
        return [
            OneXTwoLineRecord(
                source_match_id=source_match_id,
                source=self.source_name,
                bookmaker="B365",
                is_opening=False,
                is_closing=True,
                home_win_price=_float_field(row, home_field, row_number),
                draw_price=_float_field(row, draw_field, row_number),
                away_win_price=_float_field(row, away_field, row_number),
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


def _float_field(
    row: dict[str, str],
    field_name: str,
    row_number: int,
) -> float | None:
    cleaned = _clean_value(row.get(field_name))
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(
            f"football-data row {row_number}: field {field_name} must be numeric"
        ) from exc


def _int_field(
    row: dict[str, str],
    field_name: str,
    row_number: int,
) -> int | None:
    cleaned = _clean_value(row.get(field_name))
    if cleaned is None:
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(
            f"football-data row {row_number}: field {field_name} must be numeric"
        ) from exc


def _has_any_value(row: dict[str, str], field_names: tuple[str, ...]) -> bool:
    return any(
        _clean_value(row.get(field_name)) is not None
        for field_name in field_names
    )


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _slug(value: str) -> str:
    normalized = normalize_team_name(value)
    return normalized.replace(" ", "-") or "unknown"
