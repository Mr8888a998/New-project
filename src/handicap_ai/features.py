from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MatchFeatures:
    open_handicap: float | None
    close_handicap: float | None
    handicap_delta: float | None
    open_total: float | None
    close_total: float | None
    total_delta: float | None
    home_water_delta: float | None
    away_water_delta: float | None
    over_water_delta: float | None
    under_water_delta: float | None
    closing_home_win_price: float | None
    closing_draw_price: float | None
    closing_away_win_price: float | None
    movement_patterns: tuple[str, ...]
    line_depth_score: float
    market_disagreement_score: float
    data_quality_score: float


def classify_movement(
    open_line: float | None,
    close_line: float | None,
    open_price: float | None,
    close_price: float | None,
) -> str:
    if open_line is None or close_line is None:
        return "line_missing"

    line_part = "line_stable"
    depth_delta = abs(close_line) - abs(open_line)
    if depth_delta >= 0.25:
        line_part = "line_up"
    elif depth_delta <= -0.25:
        line_part = "line_down"

    price_part = "price_missing"
    if open_price is not None and close_price is not None:
        price_delta = close_price - open_price
        if price_delta <= -0.03:
            price_part = "price_down"
        elif price_delta >= 0.03:
            price_part = "price_up"
        else:
            price_part = "price_stable"

    return f"{line_part}_{price_part}"


def build_match_features(
    asian_rows: Sequence[Any],
    total_rows: Sequence[Any],
    one_x_two_rows: Sequence[Any],
) -> MatchFeatures:
    asian_rows = tuple(asian_rows)
    total_rows = tuple(total_rows)
    one_x_two_rows = tuple(one_x_two_rows)

    open_asian = _select_row(asian_rows, "is_opening")
    close_asian = _select_row(asian_rows, "is_closing") or _last_row(asian_rows)
    open_total = _select_row(total_rows, "is_opening")
    close_total = _select_row(total_rows, "is_closing") or _last_row(total_rows)
    close_1x2 = _select_row(one_x_two_rows, "is_closing") or _last_row(
        one_x_two_rows
    )

    open_handicap = _float(open_asian, "line")
    close_handicap = _float(close_asian, "line")
    open_total_line = _float(open_total, "total")
    close_total_line = _float(close_total, "total")

    patterns = (
        classify_movement(
            open_handicap,
            close_handicap,
            _float(open_asian, "home_price"),
            _float(close_asian, "home_price"),
        ),
        classify_movement(
            open_total_line,
            close_total_line,
            _float(open_total, "over_price"),
            _float(close_total, "over_price"),
        ),
    )

    return MatchFeatures(
        open_handicap=open_handicap,
        close_handicap=close_handicap,
        handicap_delta=_delta(open_handicap, close_handicap),
        open_total=open_total_line,
        close_total=close_total_line,
        total_delta=_delta(open_total_line, close_total_line),
        home_water_delta=_delta(
            _float(open_asian, "home_price"), _float(close_asian, "home_price")
        ),
        away_water_delta=_delta(
            _float(open_asian, "away_price"), _float(close_asian, "away_price")
        ),
        over_water_delta=_delta(
            _float(open_total, "over_price"), _float(close_total, "over_price")
        ),
        under_water_delta=_delta(
            _float(open_total, "under_price"), _float(close_total, "under_price")
        ),
        closing_home_win_price=_float(close_1x2, "home_win_price"),
        closing_draw_price=_float(close_1x2, "draw_price"),
        closing_away_win_price=_float(close_1x2, "away_win_price"),
        movement_patterns=patterns,
        line_depth_score=abs(close_handicap or 0.0),
        market_disagreement_score=_market_disagreement(
            close_handicap, _float(close_1x2, "home_win_price")
        ),
        data_quality_score=_data_quality(
            open_asian, close_asian, open_total, close_total, close_1x2
        ),
    )


def _select_row(rows: Sequence[Any], flag: str) -> Any | None:
    return next((row for row in rows if _truthy(_row_get(row, flag))), None)


def _last_row(rows: Sequence[Any]) -> Any | None:
    return rows[-1] if rows else None


def _row_get(row: Any | None, key: str) -> object | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return None


def _truthy(value: object | None) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _float(row: Any | None, key: str) -> float | None:
    value = _row_get(row, key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return round(end - start, 4)


def _data_quality(*rows: Any | None) -> float:
    if not rows:
        return 0.0
    present = sum(1 for row in rows if row is not None)
    return round(present / len(rows), 2)


def _market_disagreement(
    close_handicap: float | None, home_win_price: float | None
) -> float:
    if close_handicap is None or home_win_price is None:
        return 0.5
    strong_home = home_win_price <= 1.5
    deep_home_line = close_handicap <= -2.0
    return 0.2 if strong_home == deep_home_line else 0.8
